#!/usr/bin/env python3
"""
Simple syslog forwarder - receives UDP syslog and forwards to backend API.
"""

import socket
import json
import os
import threading
import logging
import re
import time
from collections import deque
from datetime import datetime, timezone

import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

_SEVERITY_NAMES = {
    "emerg": 0, "emergency": 0, "alert": 1, "crit": 2, "critical": 2,
    "err": 3, "error": 3, "warning": 4, "warn": 4, "notice": 5,
    "info": 6, "informational": 6, "debug": 7,
}


def parse_min_severity(raw: str):
    """SYSLOG_MIN_SEVERITY: a name ("notice") or number (0-7). Empty disables."""
    value = (raw or "").strip().lower()
    if not value:
        return None
    if value.isdigit() and 0 <= int(value) <= 7:
        return int(value)
    if value in _SEVERITY_NAMES:
        return _SEVERITY_NAMES[value]
    logger.warning("Ignoring invalid SYSLOG_MIN_SEVERITY=%r", raw)
    return None


# Configuration
SYSLOG_HOST = os.getenv("SYSLOG_HOST", "0.0.0.0")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", 514))
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api/syslog/ingest")
API_KEY = os.getenv("API_KEY", "syslog-secret-key")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
BATCH_TIMEOUT = float(os.getenv("BATCH_TIMEOUT", 5))
# Upper bound on queued events while the backend is unreachable; oldest go first.
MAX_BUFFER = int(os.getenv("MAX_BUFFER", 50000))
# Requested UDP receive buffer; the kernel caps it at net.core.rmem_max.
SOCKET_RCVBUF = int(os.getenv("SOCKET_RCVBUF", 4 * 1024 * 1024))
SUMMARY_INTERVAL = float(os.getenv("SUMMARY_INTERVAL", 300))
SYSLOG_MIN_SEVERITY = parse_min_severity(os.getenv("SYSLOG_MIN_SEVERITY", ""))


PROGRAM_MAX_LEN = 64  # syslog_events.program is VARCHAR(64)

_PRI_RE = re.compile(r"^<(\d{1,3})>")
# RFC 5424: VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID SD [MSG]
_RFC5424_RE = re.compile(r"^\d{1,2} \S+ \S+ (\S+) \S+ \S+ (.*)$", re.S)
_SD_RE = re.compile(r'^(?:-|(?:\[(?:[^\]\\]|\\.)*\])+)\s?(.*)$', re.S)
# Optional Cisco sequence number ("45: ") and origin hostname ("sw-oficina: ").
_CISCO_SEQ_RE = re.compile(r"^\d+:\s+")
_CISCO_HOST_RE = re.compile(r"^[A-Za-z0-9][\w.\-]*:\s+(?=[*.]?[A-Z][a-z]{2}\s)")
# RFC 3164 / Cisco timestamp: "Nov 23 17:52:31", "*Nov 23 2026 17:52:31.123 UTC:"
_TIMESTAMP_RE = re.compile(
    r"^[*.]?[A-Z][a-z]{2}\s+\d{1,2}\s+(?:\d{4}\s+)?\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:\s+[A-Z]{2,5})?:?\s+"
)
_TAG_RE = re.compile(r"^([^\s:\[]+)(?:\[\d+\])?:\s*(.*)$", re.S)
# MikroTik remote logging: "system,info,account user admin logged in ..."
_MIKROTIK_TOPICS_RE = re.compile(r"^([a-z]+(?:,[a-z]+)+)\s+(.*)$", re.S)
# RouterOS severity topics; the most severe one wins when several are present.
_MIKROTIK_SEVERITY = {"critical": 2, "error": 3, "warning": 4, "info": 6, "debug": 7}


def _mikrotik_without_pri(message: str):
    """RouterOS with bsd-syslog=no sends "topics message" and no <PRI>.

    Return (program, text, severity), or None when the line does not carry a
    RouterOS severity topic.
    """
    topics = _MIKROTIK_TOPICS_RE.match(message)
    if not topics:
        return None
    levels = [_MIKROTIK_SEVERITY[t] for t in topics.group(1).split(",") if t in _MIKROTIK_SEVERITY]
    if not levels:
        return None
    return topics.group(1), topics.group(2), min(levels)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _split_rfc3164(rest: str):
    """Return (program, message) from an RFC 3164 / vendor syslog body."""
    body = _CISCO_SEQ_RE.sub("", rest, count=1)
    body = _CISCO_HOST_RE.sub("", body, count=1)
    stamped = _TIMESTAMP_RE.match(body)
    if stamped:
        body = body[stamped.end():]
        # RFC 3164 puts HOSTNAME after the timestamp; Cisco goes straight to "%TAG:".
        first, _, remainder = body.partition(" ")
        if remainder and not first.endswith(":") and not first.startswith("%"):
            body = remainder

    tag = _TAG_RE.match(body)
    if tag:
        return tag.group(1), tag.group(2)
    topics = _MIKROTIK_TOPICS_RE.match(body)
    if topics:
        return topics.group(1), topics.group(2)
    return None, body


def parse_syslog(message: str, source_ip: str) -> dict:
    """Parse one syslog datagram.

    device_ip is always the UDP source address: the message text cannot be
    trusted to carry it (RFC 3164 headers hold a timestamp and a hostname).
    """
    facility, severity = 1, 6  # user-level / informational when PRI is missing
    program, text = None, message

    try:
        pri = _PRI_RE.match(message)
        if pri:
            priority = int(pri.group(1))
            facility, severity = priority >> 3, priority & 7
            rest = message[pri.end():]
            rfc5424 = _RFC5424_RE.match(rest)
            if rfc5424:
                app, after_header = rfc5424.groups()
                program = None if app == "-" else app
                sd = _SD_RE.match(after_header)
                text = sd.group(1) if sd else after_header
            else:
                program, text = _split_rfc3164(rest)
        else:
            mikrotik = _mikrotik_without_pri(message)
            if mikrotik:
                program, text, severity = mikrotik
    except Exception as e:
        logger.warning(f"Failed to parse syslog: {e}")
        program, text = None, message

    return {
        "device_ip": source_ip,
        "program": program[:PROGRAM_MAX_LEN] if program else None,
        "message": text.strip() or message,
        "facility": facility,
        "severity": severity,
        "received_at": _utc_now(),
    }


def post_to_backend(batch) -> bool:
    """POST one batch. Returns False on a non-2xx reply; network errors raise."""
    response = requests.post(
        BACKEND_URL,
        json=batch,
        headers={"Content-Type": "application/json", "X-API-Key": API_KEY},
        timeout=10,
    )
    if response.status_code in (200, 201):
        return True
    logger.warning("Backend returned %s: %s", response.status_code, response.text[:200])
    return False


class Forwarder:
    """Bounded event queue drained in batches by a sender thread.

    The UDP receive loop only calls submit(), so it never waits on the backend.
    """

    def __init__(self, send, batch_size=50, batch_timeout=5.0, max_buffer=50000,
                 min_severity=None):
        self._send = send
        self._batch_size = max(1, batch_size)
        self._batch_timeout = batch_timeout
        self._max_buffer = max(1, max_buffer)
        self._min_severity = min_severity
        self._buffer = deque()
        self._oldest_at = None  # monotonic time the oldest queued event arrived
        self._cond = threading.Condition()
        self._stats = dict.fromkeys(
            ("received", "filtered", "dropped", "forwarded", "failed_posts"), 0
        )

    def submit(self, event) -> None:
        with self._cond:
            self._stats["received"] += 1
            if self._min_severity is not None and event.get("severity", 6) > self._min_severity:
                self._stats["filtered"] += 1
                return
            if not self._buffer:
                self._oldest_at = time.monotonic()
            self._buffer.append(event)
            self._trim()
            if len(self._buffer) >= self._batch_size:
                self._cond.notify()

    def _trim(self) -> None:
        while len(self._buffer) > self._max_buffer:
            self._buffer.popleft()
            self._stats["dropped"] += 1

    def pending(self):
        with self._cond:
            return list(self._buffer)

    def stats(self):
        with self._cond:
            return dict(self._stats)

    def wake(self) -> None:
        with self._cond:
            self._cond.notify_all()

    def _ready(self) -> bool:
        if len(self._buffer) >= self._batch_size:
            return True
        return bool(self._buffer) and time.monotonic() - self._oldest_at >= self._batch_timeout

    def next_batch(self, stop=None):
        """Block until a full batch is queued or the oldest event is BATCH_TIMEOUT old.

        When stop is set, return whatever is queued (possibly empty).
        """
        with self._cond:
            while not self._ready() and not (stop is not None and stop.is_set()):
                if self._buffer:
                    remaining = self._batch_timeout - (time.monotonic() - self._oldest_at)
                    self._cond.wait(max(remaining, 0.001))
                else:
                    self._cond.wait(1.0 if stop is not None else None)
            count = min(self._batch_size, len(self._buffer))
            batch = [self._buffer.popleft() for _ in range(count)]
            # Remaining events are treated as fresh so the next partial batch
            # waits a full timeout instead of being flushed immediately.
            self._oldest_at = time.monotonic() if self._buffer else None
            return batch

    def deliver(self, batch) -> bool:
        """Send one batch; on failure put it back at the front of the queue."""
        if not batch:
            return True
        try:
            ok = self._send(batch)
        except Exception as e:
            logger.error("Failed to forward %d messages: %s", len(batch), e)
            ok = False
        with self._cond:
            if ok:
                self._stats["forwarded"] += len(batch)
                return True
            self._stats["failed_posts"] += 1
            if not self._buffer:
                self._oldest_at = time.monotonic()
            self._buffer.extendleft(reversed(batch))
            self._trim()
            return False

    def run(self, stop) -> None:
        """Sender loop; flushes what is left when stop is set."""
        while True:
            batch = self.next_batch(stop)
            if stop.is_set():
                if batch:
                    self.deliver(batch)
                return
            if not self.deliver(batch):
                stop.wait(self._batch_timeout)  # backend down: back off before retrying


FORWARDER = Forwarder(
    send=post_to_backend,
    batch_size=BATCH_SIZE,
    batch_timeout=BATCH_TIMEOUT,
    max_buffer=MAX_BUFFER,
    min_severity=SYSLOG_MIN_SEVERITY,
)


def handle_client(data, addr):
    """Parse one datagram and queue it; never blocks on the backend."""
    try:
        message = data.decode("utf-8", errors="replace").strip()
        if not message:
            return
        FORWARDER.submit(parse_syslog(message, addr[0]))
    except Exception as e:
        logger.error(f"Error handling message from {addr}: {e}")


def summary_worker(stop) -> None:
    """Log one line of counters per interval instead of one line per message."""
    previous = FORWARDER.stats()
    while not stop.wait(SUMMARY_INTERVAL):
        current = FORWARDER.stats()
        delta = {k: current[k] - previous[k] for k in current}
        logger.info(
            "Last %ds: received=%d filtered=%d forwarded=%d dropped=%d failed_posts=%d queued=%d",
            SUMMARY_INTERVAL, delta["received"], delta["filtered"], delta["forwarded"],
            delta["dropped"], delta["failed_posts"], len(FORWARDER.pending()),
        )
        previous = current


def open_udp_socket(host, port, rcvbuf=SOCKET_RCVBUF):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
    except OSError as e:
        logger.warning("Could not set SO_RCVBUF=%d: %s", rcvbuf, e)
    sock.bind((host, port))
    return sock


def main():
    logger.info(f"Starting syslog forwarder on {SYSLOG_HOST}:{SYSLOG_PORT}")
    logger.info(
        "Forwarding to %s (batch_size=%d, batch_timeout=%ss, max_buffer=%d, min_severity=%s)",
        BACKEND_URL, BATCH_SIZE, BATCH_TIMEOUT, MAX_BUFFER, SYSLOG_MIN_SEVERITY,
    )

    stop = threading.Event()
    threading.Thread(target=FORWARDER.run, args=(stop,), daemon=True).start()
    threading.Thread(target=summary_worker, args=(stop,), daemon=True).start()

    sock = open_udp_socket(SYSLOG_HOST, SYSLOG_PORT)
    logger.info(
        "Listening on %s:%s (SO_RCVBUF=%d)",
        SYSLOG_HOST, SYSLOG_PORT, sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF),
    )

    while True:
        try:
            data, addr = sock.recvfrom(8192)
            handle_client(data, addr)
        except Exception as e:
            logger.error(f"Error receiving data: {e}")


if __name__ == "__main__":
    main()
