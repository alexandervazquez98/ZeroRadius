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
import requests
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
SYSLOG_HOST = os.getenv("SYSLOG_HOST", "0.0.0.0")
SYSLOG_PORT = int(os.getenv("SYSLOG_PORT", 514))
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000/api/syslog/ingest")
API_KEY = os.getenv("API_KEY", "syslog-secret-key")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 50))
BATCH_TIMEOUT = int(os.getenv("BATCH_TIMEOUT", 5))

# Buffer for batching
message_buffer = []
buffer_lock = threading.Lock()
last_flush = datetime.now()


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


def flush_buffer():
    """Flush the message buffer to the backend."""
    global message_buffer, last_flush

    with buffer_lock:
        if not message_buffer:
            return

        to_send = message_buffer.copy()
        message_buffer.clear()
        last_flush = datetime.now()

    if to_send:
        try:
            headers = {"Content-Type": "application/json", "X-API-Key": API_KEY}
            logger.info(f"Sending {len(to_send)} messages to {BACKEND_URL}")
            response = requests.post(
                BACKEND_URL, json=to_send, headers=headers, timeout=10
            )
            logger.info(
                f"Backend response: {response.status_code} - {response.text[:200]}"
            )
            if response.status_code in (200, 201):
                logger.info(f"Forwarded {len(to_send)} messages to backend")
            else:
                logger.warning(
                    f"Backend returned {response.status_code}: {response.text}"
                )
                # Put messages back in buffer
                with buffer_lock:
                    message_buffer.extend(to_send)
        except Exception as e:
            logger.error(f"Failed to forward messages: {e}")
            # Put messages back in buffer
            with buffer_lock:
                message_buffer.extend(to_send)


def flush_worker():
    """Periodically flush the buffer."""
    while True:
        import time

        time.sleep(BATCH_TIMEOUT)

        with buffer_lock:
            should_flush = len(message_buffer) >= BATCH_SIZE

        if should_flush:
            flush_buffer()


def handle_client(data, addr):
    """Handle incoming syslog message."""
    try:
        message = data.decode("utf-8", errors="replace").strip()
        if not message:
            return

        parsed = parse_syslog(message, addr[0])
        logger.info(f"Received from {addr}: {message[:50]}...")

        with buffer_lock:
            message_buffer.append(parsed)

        # Flush immediately (outside lock to avoid deadlock)
        if len(message_buffer) >= 1:
            flush_buffer()

    except Exception as e:
        logger.error(f"Error handling message from {addr}: {e}")


def main():
    logger.info(f"Starting syslog forwarder on {SYSLOG_HOST}:{SYSLOG_PORT}")
    logger.info(f"Forwarding to {BACKEND_URL}")

    # Start flush worker
    flush_thread = threading.Thread(target=flush_worker, daemon=True)
    flush_thread.start()

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((SYSLOG_HOST, SYSLOG_PORT))

    logger.info(f"Listening on {SYSLOG_HOST}:{SYSLOG_PORT}")

    while True:
        try:
            data, addr = sock.recvfrom(4096)
            handle_client(data, addr)
        except Exception as e:
            logger.error(f"Error receiving data: {e}")


if __name__ == "__main__":
    main()
