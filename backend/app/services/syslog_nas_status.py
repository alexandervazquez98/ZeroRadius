"""
NAS syslog reporting status.

Every registered NAS is expected to send syslog. A NAS is *silent* when no
event arrived from it within the threshold (``SYSLOG_SILENT_HOURS``, default
24 h). Matching against ``syslog_events.device_ip``:

- IP ``nasname``: exact address match.
- CIDR ``nasname``: any address inside the network counts.
- Hostname ``nasname``: exact string match only (syslog stores source IPs).
"""

from __future__ import annotations

import ipaddress
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Nas, SyslogEvent

logger = logging.getLogger(__name__)

DEFAULT_SILENT_HOURS = 24


def silent_threshold_hours() -> int:
    raw = os.getenv("SYSLOG_SILENT_HOURS", "")
    try:
        value = int(raw)
        if value >= 1:
            return value
    except ValueError:
        pass
    if raw.strip():
        logger.warning(
            "Invalid SYSLOG_SILENT_HOURS=%r; using default %d", raw, DEFAULT_SILENT_HOURS
        )
    return DEFAULT_SILENT_HOURS


def _last_seen_for(nasname: str, last_seen_by_ip: dict[str, datetime]) -> Optional[datetime]:
    if nasname in last_seen_by_ip:
        return last_seen_by_ip[nasname]
    if "/" not in nasname:
        return None
    try:
        network = ipaddress.ip_network(nasname, strict=False)
    except ValueError:
        return None
    seen = []
    for ip, ts in last_seen_by_ip.items():
        try:
            if ipaddress.ip_address(ip) in network:
                seen.append(ts)
        except ValueError:
            continue
    return max(seen, default=None)


async def get_nas_syslog_status(db: AsyncSession, hours: Optional[int] = None) -> dict:
    threshold_hours = hours if hours is not None else silent_threshold_hours()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=threshold_hours)

    rows = await db.execute(
        select(SyslogEvent.device_ip, func.max(SyslogEvent.received_at)).group_by(
            SyslogEvent.device_ip
        )
    )
    last_seen_by_ip = {ip: ts for ip, ts in rows.all() if ts is not None}

    nas_rows = (await db.execute(select(Nas).order_by(Nas.nasname))).scalars().all()

    devices = []
    for nas in nas_rows:
        last_seen = _last_seen_for(nas.nasname, last_seen_by_ip)
        devices.append(
            {
                "id": nas.id,
                "nasname": nas.nasname,
                "shortname": nas.shortname,
                "last_seen": last_seen,
                "silent": last_seen is None or last_seen < cutoff,
            }
        )

    # Silent first; within each group, the longest-silent devices first.
    devices.sort(
        key=lambda d: (not d["silent"], d["last_seen"] is not None, d["last_seen"] or now)
    )

    silent_count = sum(1 for d in devices if d["silent"])
    return {
        "threshold_hours": threshold_hours,
        "total": len(devices),
        "silent_count": silent_count,
        "reporting_count": len(devices) - silent_count,
        "devices": devices,
    }
