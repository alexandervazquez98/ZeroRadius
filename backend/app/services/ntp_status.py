"""
NTPStatusService — ISO 27001 A.8.17

Measures the clock offset with one SNTP request (RFC 4330) to NTP_SERVER.
The backend container shares the host clock, so this is the host's real
offset whatever time daemon the host runs (chrony, ntpd, systemd-timesyncd).

NTP_SERVER is "host" or "host:port" (default port 123). When it is unset the
status is "not configured", not an alarm. Results are cached for 60 seconds.

Blocking (UDP socket): call get_status() from a worker thread.
"""

import logging
import os
import socket
import struct
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Cache duration in seconds
NTP_CACHE_TTL = 60

# Alert threshold: offset in milliseconds
NTP_ALERT_OFFSET_MS = 500.0

# Seconds to wait for the SNTP reply
SNTP_TIMEOUT = 2.0

NTP_PORT = 123
_NTP_EPOCH_DELTA = 2208988800  # seconds between 1900-01-01 and 1970-01-01
_PACKET_LEN = 48
_MODE_SERVER = 4

_cache_lock = threading.Lock()
_ntp_cache: Optional["NTPStatus"] = None
_ntp_cache_time: float = 0.0


@dataclass
class NTPStatus:
    synchronized: bool
    offset_ms: float
    stratum: Optional[int]
    reference_server: Optional[str]
    last_sync: Optional[str]
    alert: bool
    configured: bool = True


def clear_cache() -> None:
    """Drop the cached status (used by tests)."""
    global _ntp_cache, _ntp_cache_time
    with _cache_lock:
        _ntp_cache = None
        _ntp_cache_time = 0.0


def _parse_server(value: str) -> tuple[str, int]:
    host, sep, port = value.rpartition(":")
    if sep and port.isdigit():
        return host, int(port)
    return value, NTP_PORT


def _to_ntp(ts: float) -> bytes:
    secs = int(ts) + _NTP_EPOCH_DELTA
    frac = int((ts % 1) * 2**32) & 0xFFFFFFFF
    return struct.pack("!II", secs, frac)


def _from_ntp(data: bytes) -> float:
    secs, frac = struct.unpack("!II", data)
    return secs - _NTP_EPOCH_DELTA + frac / 2**32


def _query(host: str, port: int) -> tuple[float, int]:
    """
    Send one SNTP request. Returns (offset_seconds, server_stratum).
    Raises ValueError for an invalid reply and OSError on network errors.
    """
    t1 = time.time()
    transmit = _to_ntp(t1)
    # LI=0, VN=4, Mode=3 (client); our transmit timestamp at bytes 40-47.
    request = bytes([0x23]) + b"\x00" * 39 + transmit
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(SNTP_TIMEOUT)
        sock.sendto(request, (host, port))
        data, _ = sock.recvfrom(512)
    t4 = time.time()

    if len(data) < _PACKET_LEN:
        raise ValueError("short SNTP reply")
    mode = data[0] & 0x07
    stratum = data[1]
    if mode != _MODE_SERVER:
        raise ValueError(f"not a server reply (mode {mode})")
    if not 1 <= stratum <= 15:
        raise ValueError(f"server not synchronized (stratum {stratum})")
    if data[24:32] != transmit:
        raise ValueError("reply does not match our request")

    t2 = _from_ntp(data[32:40])  # server receive
    t3 = _from_ntp(data[40:48])  # server transmit
    offset = ((t2 - t1) + (t3 - t4)) / 2
    return offset, stratum


def _measure() -> NTPStatus:
    server = os.getenv("NTP_SERVER", "").strip()
    if not server:
        return NTPStatus(
            synchronized=False, offset_ms=0.0, stratum=None, reference_server=None,
            last_sync=None, alert=False, configured=False,
        )
    host, port = _parse_server(server)
    try:
        offset, stratum = _query(host, port)
    except (OSError, ValueError) as e:
        logger.warning("NTP check against %s failed: %s", server, e)
        return NTPStatus(
            synchronized=False, offset_ms=0.0, stratum=None, reference_server=server,
            last_sync=None, alert=True,
        )
    offset_ms = abs(offset) * 1000
    return NTPStatus(
        synchronized=True,
        offset_ms=round(offset_ms, 3),
        stratum=stratum,
        reference_server=server,
        last_sync=datetime.now(timezone.utc).isoformat(),
        alert=offset_ms > NTP_ALERT_OFFSET_MS,
    )


def get_status() -> NTPStatus:
    """Current NTP status, cached for NTP_CACHE_TTL seconds."""
    global _ntp_cache, _ntp_cache_time
    with _cache_lock:
        now = time.monotonic()
        if _ntp_cache is None or now - _ntp_cache_time >= NTP_CACHE_TTL:
            _ntp_cache = _measure()
            _ntp_cache_time = time.monotonic()
        return _ntp_cache
