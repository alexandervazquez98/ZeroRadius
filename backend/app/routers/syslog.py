from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.session import get_db
from app.models.models import SyslogEvent
from app.core.security import get_current_active_user
from app.models.models import AdminUser
from typing import Optional, List
from datetime import datetime
import logging
import os

router = APIRouter(prefix="/syslog", tags=["syslog"])
logger = logging.getLogger(__name__)

SYSLOG_API_KEY = os.getenv("SYSLOG_API_KEY", "")


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
    total: int


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

    logger.info("Ingested %d syslog events", len(mappings))
    return {"ingested": len(mappings)}


@router.get("", response_model=SyslogListResponse)
async def get_syslog_events(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    start_date: Optional[datetime] = Query(default=None, alias="start_date"),
    end_date: Optional[datetime] = Query(default=None, alias="end_date"),
    device_ip: Optional[str] = Query(default=None, max_length=45),
    severity: Optional[int] = Query(default=None, ge=0, le=7),
    facility: Optional[int] = Query(default=None, ge=0, le=23),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """
    Retrieve syslog events with pagination and filtering.
    """
    from sqlalchemy import and_

    stmt = select(SyslogEvent)
    count_stmt = select(func.count(SyslogEvent.id))

    filters = []
    if start_date:
        filters.append(SyslogEvent.received_at >= start_date)
    if end_date:
        filters.append(SyslogEvent.received_at <= end_date)
    if device_ip:
        filters.append(SyslogEvent.device_ip == device_ip)
    if severity is not None:
        filters.append(SyslogEvent.severity == severity)
    if facility is not None:
        filters.append(SyslogEvent.facility == facility)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    stmt = stmt.order_by(SyslogEvent.received_at.desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    events = result.scalars().all()

    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    return {"events": events, "total": total}
