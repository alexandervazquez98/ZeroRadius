from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.db.session import get_db
from app.models.models import SyslogEvent
from app.core.security import get_current_active_user
from app.models.models import AdminUser
from typing import Optional, List
from datetime import datetime, timedelta, timezone
import base64
import binascii
import logging
import os

router = APIRouter(prefix="/syslog", tags=["syslog"])
logger = logging.getLogger(__name__)

SYSLOG_API_KEY = os.getenv("SYSLOG_API_KEY", "")
# The list endpoint never reads more than this window, so a query stays
# bounded however large syslog_events grows (#136).
SYSLOG_QUERY_MAX_HOURS = int(os.getenv("SYSLOG_QUERY_MAX_HOURS", "8"))


def _utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """received_at is stored as naive UTC; drop any offset after converting."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def resolve_window(start: Optional[datetime], end: Optional[datetime], now: datetime):
    """Return the (start, end) window to query, at most SYSLOG_QUERY_MAX_HOURS long."""
    span = timedelta(hours=SYSLOG_QUERY_MAX_HOURS)
    if start is None and end is None:
        end = now
    if start is None:
        start = end - span
    if end is None:
        end = start + span
    if end < start:
        raise HTTPException(status_code=422, detail="end_date must be after start_date.")
    if end - start > span:
        raise HTTPException(
            status_code=422,
            detail=f"The time range cannot exceed {SYSLOG_QUERY_MAX_HOURS} hours.",
        )
    return start, end


def encode_cursor(event) -> str:
    raw = f"{event.received_at.isoformat()}|{event.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str):
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        stamp, _, event_id = base64.urlsafe_b64decode(padded).decode().partition("|")
        return datetime.fromisoformat(stamp), int(event_id)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise HTTPException(status_code=422, detail="Invalid cursor.")


def _like_literal(text: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SyslogEventIn(BaseModel):
    received_at: datetime
    device_ip: str
    facility: Optional[int] = None
    severity: Optional[int] = None
    program: Optional[str] = None
    message: str


class SyslogEventOut(BaseModel):
    id: int
    received_at: datetime
    device_ip: str
    facility: Optional[int]
    severity: Optional[int]
    program: Optional[str]
    message: str
    previous_hash: Optional[str]
    hash: Optional[str]

    class Config:
        from_attributes = True


class SyslogListResponse(BaseModel):
    events: List[SyslogEventOut]
    has_more: bool
    next_cursor: Optional[str]
    start_date: datetime
    end_date: datetime
    max_range_hours: int


class NasSyslogStatusOut(BaseModel):
    id: int
    nasname: str
    shortname: Optional[str]
    last_seen: Optional[datetime]
    silent: bool


class NasSyslogStatusResponse(BaseModel):
    threshold_hours: int
    total: int
    silent_count: int
    reporting_count: int
    devices: List[NasSyslogStatusOut]


@router.get("/nas-status", response_model=NasSyslogStatusResponse)
async def get_nas_syslog_status_endpoint(
    hours: Optional[int] = Query(default=None, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """
    Report which registered NAS have not sent syslog within the threshold.
    Threshold defaults to SYSLOG_SILENT_HOURS (24 h); `hours` overrides it.
    """
    from app.services.syslog_nas_status import get_nas_syslog_status

    return await get_nas_syslog_status(db, hours)


@router.post("/ingest", status_code=201, response_model=dict)
async def ingest_syslog_events(
    events: List[SyslogEventIn],
    db: AsyncSession = Depends(get_db),
    x_api_key: Optional[str] = Header(None, alias="x-api-key"),
):
    """
    Bulk ingest syslog events from rsyslog.
    Accepts a JSON array of syslog events and bulk inserts them.
    Hash chain is calculated by the background worker.
    Can use x-api-key header for authentication (optional, falls back to session auth).
    """
    if SYSLOG_API_KEY and x_api_key != SYSLOG_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not events:
        raise HTTPException(status_code=400, detail="No events provided")

    mappings = []
    for event in events:
        mappings.append(
            {
                "received_at": event.received_at,
                "device_ip": event.device_ip,
                "facility": event.facility,
                "severity": event.severity,
                "program": event.program,
                "message": event.message,
            }
        )

    await db.run_sync(
        lambda sync_db: sync_db.execute(SyslogEvent.__table__.insert(), mappings)
    )
    await db.commit()

    logger.debug("Ingested %d syslog events", len(mappings))
    return {"ingested": len(mappings)}


@router.get("", response_model=SyslogListResponse)
async def get_syslog_events(
    limit: int = Query(default=50, ge=1, le=500),
    cursor: Optional[str] = Query(default=None, max_length=200),
    start_date: Optional[datetime] = Query(default=None, alias="start_date"),
    end_date: Optional[datetime] = Query(default=None, alias="end_date"),
    device_ip: Optional[str] = Query(default=None, max_length=45),
    message: Optional[str] = Query(default=None, max_length=500),
    severity: Optional[int] = Query(default=None, ge=0, le=7),
    facility: Optional[int] = Query(default=None, ge=0, le=23),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """
    List syslog events newest first within a time window.

    The window defaults to the last SYSLOG_QUERY_MAX_HOURS (8) hours and can
    never be longer. Pages are keyset-paginated: pass `next_cursor` from the
    previous response as `cursor`. There is no total count.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start, end = resolve_window(_utc_naive(start_date), _utc_naive(end_date), now)

    filters = [SyslogEvent.received_at >= start, SyslogEvent.received_at <= end]
    if cursor:
        cursor_at, cursor_id = decode_cursor(cursor)
        filters.append(
            or_(
                SyslogEvent.received_at < cursor_at,
                and_(SyslogEvent.received_at == cursor_at, SyslogEvent.id < cursor_id),
            )
        )
    if device_ip:
        # Prefix match ("192.168" matches "192.168.1.50"); can use the
        # (device_ip, received_at) index, unlike ILIKE, which wraps LOWER().
        filters.append(SyslogEvent.device_ip.like(f"{_like_literal(device_ip)}%", escape="\\"))
    if message:
        filters.append(SyslogEvent.message.ilike(f"%{_like_literal(message)}%", escape="\\"))
    if severity is not None:
        filters.append(SyslogEvent.severity == severity)
    if facility is not None:
        filters.append(SyslogEvent.facility == facility)

    stmt = (
        select(SyslogEvent)
        .where(and_(*filters))
        .order_by(SyslogEvent.received_at.desc(), SyslogEvent.id.desc())
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    has_more = len(rows) > limit
    events = rows[:limit]

    return {
        "events": events,
        "has_more": has_more,
        "next_cursor": encode_cursor(events[-1]) if has_more else None,
        "start_date": start,
        "end_date": end,
        "max_range_hours": SYSLOG_QUERY_MAX_HOURS,
    }
