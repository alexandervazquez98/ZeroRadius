from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.db.session import get_db
from app.models.models import AppAuditLog, AdminUser, RadPostAuth
from app.schemas.schemas import AuditLogOut, RadPostAuthOut, SIEMEvent
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.services.audit import log_audit, EventCode
from typing import Optional
from datetime import datetime
import json
import csv
import io

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/admin", response_model=list[AuditLogOut])
async def get_admin_audit_logs(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List administrative action logs."""
    stmt = select(AppAuditLog).order_by(AppAuditLog.timestamp.desc())

    if search:
        search_filter = f"%{search}%"
        stmt = stmt.where(
            or_(
                AppAuditLog.admin_user.ilike(search_filter),
                AppAuditLog.action.ilike(search_filter),
                AppAuditLog.table_affected.ilike(search_filter),
                AppAuditLog.target_user.ilike(search_filter),
            )
        )

    result = await db.execute(stmt.offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/access", response_model=list[RadPostAuthOut])
async def get_access_logs(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    nas_ip: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List RADIUS authentication attempts (Access-Accept/Reject) with NAS traceability."""
    stmt = select(RadPostAuth).order_by(RadPostAuth.authdate.desc())

    filters = []
    if search:
        search_filter = f"%{search}%"
        filters.append(
            or_(
                RadPostAuth.username.ilike(search_filter),
                RadPostAuth.reply.ilike(search_filter),
            )
        )
    if nas_ip:
        filters.append(RadPostAuth.nas_ip_address == nas_ip)

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt.offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/export")
async def export_audit_siem(
    format: str = Query("json", pattern="^(json|csv)$"),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    event_type: Optional[str] = Query(None, pattern="^(AUTH|ACCT|ADMIN)?$"),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    """
    SIEM export endpoint — returns audit logs in JSON or CSV format.
    Requires auditor, admin, or superadmin role.
    Logs ADMIN-008 event on each call.
    """
    stmt = select(AppAuditLog).order_by(AppAuditLog.timestamp.desc())

    # Date filtering
    if from_date:
        try:
            dt_from = datetime.fromisoformat(from_date)
            stmt = stmt.where(AppAuditLog.timestamp >= dt_from)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Invalid 'from' date format. Use ISO 8601."
            )

    if to_date:
        try:
            dt_to = datetime.fromisoformat(to_date)
            stmt = stmt.where(AppAuditLog.timestamp <= dt_to)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Invalid 'to' date format. Use ISO 8601."
            )

    # Event type filter (prefix match on action)
    if event_type:
        stmt = stmt.where(AppAuditLog.action.ilike(f"%{event_type}%"))

    result = await db.execute(stmt)
    records = result.scalars().all()

    # Log ADMIN-008 audit export event
    await log_audit(
        db,
        admin_user=current_user.username,
        action=f"SIEM export ({format}, {len(records)} records)",
        table_affected="app_audit_log",
        target_user=None,
        event_code=EventCode.ADMIN_008,
    )

    # Build SIEM events
    siem_events = [
        {
            "event_id": r.id,
            "timestamp_utc": r.timestamp.isoformat() if r.timestamp else None,
            "identity": {
                "admin_user": r.admin_user,
                "target_user": r.target_user,
            },
            "action": r.action,
            "table_affected": r.table_affected,
            "authorization_result": None,
            "old_value": json.loads(r.old_value) if r.old_value else None,
            "new_value": json.loads(r.new_value) if r.new_value else None,
        }
        for r in records
    ]

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "event_id",
                "timestamp_utc",
                "admin_user",
                "target_user",
                "action",
                "table_affected",
            ],
        )
        writer.writeheader()
        for ev in siem_events:
            writer.writerow(
                {
                    "event_id": ev["event_id"],
                    "timestamp_utc": ev["timestamp_utc"],
                    "admin_user": ev["identity"]["admin_user"],
                    "target_user": ev["identity"]["target_user"],
                    "action": ev["action"],
                    "table_affected": ev["table_affected"],
                }
            )
        csv_content = output.getvalue()
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
        )

    # JSON response: stream for large datasets, regular for small
    if len(siem_events) >= 1000:

        def generate():
            yield "["
            for i, ev in enumerate(siem_events):
                yield json.dumps(ev)
                if i < len(siem_events) - 1:
                    yield ","
            yield "]"

        return StreamingResponse(generate(), media_type="application/json")

    return JSONResponse(content=siem_events)
