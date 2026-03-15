"""
NTPStatusService — ISO 27001 A.8.17
Checks NTP synchronization status using chronyc or ntpq.
Result is cached for 60 seconds.
"""

import subprocess
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Cache duration in seconds
NTP_CACHE_TTL = 60

# Alert threshold: offset in milliseconds
NTP_ALERT_OFFSET_MS = 500.0

# Module-level cache
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


def _parse_chronyc_output(output: str) -> NTPStatus:
    """Parse output from `chronyc tracking`."""
    synchronized = False
    offset_ms = 0.0
    stratum: Optional[int] = None
    reference_server: Optional[str] = None
    last_sync: Optional[str] = None

    for line in output.splitlines():
        line_lower = line.lower()

        if "reference id" in line_lower:
            # Extract hostname/IP from parentheses if present
            match = re.search(r"\(([^)]+)\)", line)
            if match:
                reference_server = match.group(1)

        elif "stratum" in line_lower:
            match = re.search(r"(\d+)", line)
            if match:
                stratum = int(match.group(1))
                synchronized = stratum < 16  # stratum 16 means unsynced

        elif "system time" in line_lower or "rms offset" in line_lower:
            match = re.search(r"([-\d.]+)\s*seconds", line, re.IGNORECASE)
            if match:
                offset_ms = abs(float(match.group(1))) * 1000

        elif "last offset" in line_lower:
            match = re.search(r"([-\d.]+)\s*seconds", line, re.IGNORECASE)
            if match:
                offset_ms = abs(float(match.group(1))) * 1000

    alert = not synchronized or offset_ms > NTP_ALERT_OFFSET_MS
    return NTPStatus(
        synchronized=synchronized,
        offset_ms=offset_ms,
        stratum=stratum,
        reference_server=reference_server,
        last_sync=None,
        alert=alert,
    )


def _parse_ntpq_output(output: str) -> NTPStatus:
    """Parse output from `ntpq -p`."""
    synchronized = False
    offset_ms = 0.0
    stratum: Optional[int] = None
    reference_server: Optional[str] = None

    for line in output.splitlines():
        # Active peer is marked with '*'
        if line.startswith("*"):
            parts = line.split()
            if len(parts) >= 10:
                synchronized = True
                reference_server = parts[0].lstrip("*")
                try:
                    stratum = int(parts[2])
                    offset_ms = abs(float(parts[8]))  # offset in ms
                except (ValueError, IndexError):
                    pass
            break

    alert = not synchronized or offset_ms > NTP_ALERT_OFFSET_MS
    return NTPStatus(
        synchronized=synchronized,
        offset_ms=offset_ms,
        stratum=stratum,
        reference_server=reference_server,
        last_sync=None,
        alert=alert,
    )


def get_status() -> NTPStatus:
    """
    Get current NTP status. Results are cached for NTP_CACHE_TTL seconds.
    Tries chronyc first, falls back to ntpq, then returns an alert state if both fail.
    """
    global _ntp_cache, _ntp_cache_time

    now = time.monotonic()
    if _ntp_cache is not None and (now - _ntp_cache_time) < NTP_CACHE_TTL:
        return _ntp_cache

    # Try chronyc first
    try:
        result = subprocess.run(
            ["chronyc", "tracking"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            status = _parse_chronyc_output(result.stdout)
            _ntp_cache = status
            _ntp_cache_time = now
            return status
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.debug("chronyc not available, trying ntpq")

    # Fall back to ntpq
    try:
        result = subprocess.run(
            ["ntpq", "-p"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            status = _parse_ntpq_output(result.stdout)
            _ntp_cache = status
            _ntp_cache_time = now
            return status
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("Neither chronyc nor ntpq available for NTP status check")

    # Both failed — return alert state
    fallback = NTPStatus(
        synchronized=False,
        offset_ms=0.0,
        stratum=None,
        reference_server=None,
        last_sync=None,
        alert=True,
    )
    _ntp_cache = fallback
    _ntp_cache_time = now
    return fallback
