from __future__ import annotations

from datetime import datetime
from typing import Optional
import ipaddress
import re

from fastapi import HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.models import AccessPolicyAssignment, NetworkSegment, _build_segment_target_key
from app.schemas.access_policies import AccessPolicyAssignmentOut, AccessPolicyAssignmentCreate


def compute_days_until_review(review_date: Optional[datetime]) -> Optional[int]:
    """Compute days until review. Negative means overdue."""
    if review_date is None:
        return None
    today = datetime.utcnow().date()
    delta = review_date.date() - today
    return delta.days


# Aliasing the canonical builder from models to service layer
build_segment_target_key = _build_segment_target_key


def raise_nas_conflict(payload: AccessPolicyAssignmentCreate):
    if payload.nas_ip and payload.calling_station_id:
        detail = f"Access policy entry for user {payload.username} at NAS {payload.nas_ip} with MAC {payload.calling_station_id} already exists"
    elif payload.calling_station_id:
        detail = f"Access policy entry for user {payload.username} with MAC {payload.calling_station_id} already exists"
    elif payload.nas_ip:
        detail = f"Access policy entry for user {payload.username} at NAS {payload.nas_ip} already exists"
    elif (
        payload.segment_id is not None
        and payload.target_start_ip is None
        and payload.target_end_ip is None
    ):
        detail = "A base policy for this user and network segment already exists"
    else:
        detail = "Access policy entry already exists"
    
    raise HTTPException(status_code=409, detail=detail)


def is_unique_integrity_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)

    # Prefer structured driver metadata first (SQLSTATE/errno)
    if orig is not None:
        sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
        if isinstance(sqlstate, str) and sqlstate == "23505":
            return True

        errno = getattr(orig, "errno", None)
        if errno is None:
            args = getattr(orig, "args", ())
            if args and isinstance(args[0], int):
                errno = args[0]

        # MySQL/MariaDB duplicate key (1062)
        if errno == 1062:
            return True

        sqlite_errorcode = getattr(orig, "sqlite_errorcode", None)
        if sqlite_errorcode in {1555, 2067}:
            return True

        sqlite_errorname = getattr(orig, "sqlite_errorname", None)
        if sqlite_errorname in {"SQLITE_CONSTRAINT_PRIMARYKEY", "SQLITE_CONSTRAINT_UNIQUE"}:
            return True

    # Last resort fallback for drivers/messages without structured fields.
    detail = str(getattr(exc, "orig", exc)).lower()
    return (
        "duplicate entry" in detail
        or "duplicate key" in detail
        or "unique constraint" in detail
    )


def raise_assignment_integrity_error(
    payload: AccessPolicyAssignmentCreate, exc: IntegrityError
) -> None:
    if is_unique_integrity_error(exc):
        raise_nas_conflict(payload)

    raise HTTPException(
        status_code=422,
        detail="Access policy assignment violates data integrity constraints",
    ) from exc


async def find_existing_assignment(
    db: AsyncSession,
    payload: AccessPolicyAssignmentCreate,
) -> AccessPolicyAssignment | None:
    filters = [AccessPolicyAssignment.username == payload.username]

    if payload.calling_station_id and payload.nas_ip:
        filters.extend(
            [
                AccessPolicyAssignment.calling_station_id == payload.calling_station_id,
                AccessPolicyAssignment.nas_ip == payload.nas_ip,
            ]
        )
    elif payload.calling_station_id:
        filters.extend(
            [
                AccessPolicyAssignment.calling_station_id == payload.calling_station_id,
                AccessPolicyAssignment.nas_ip.is_(None),
            ]
        )
    elif payload.nas_ip:
        filters.extend(
            [
                AccessPolicyAssignment.nas_ip == payload.nas_ip,
                AccessPolicyAssignment.calling_station_id.is_(None),
                AccessPolicyAssignment.segment_id.is_(None),
                AccessPolicyAssignment.nas_category_id.is_(None),
            ]
        )
    elif payload.nas_category_id is not None:
        filters.extend(
            [
                AccessPolicyAssignment.nas_category_id == payload.nas_category_id,
                AccessPolicyAssignment.nas_ip.is_(None),
                AccessPolicyAssignment.segment_id.is_(None),
            ]
        )
    else:
        filters.extend(
            [
                AccessPolicyAssignment.segment_id == payload.segment_id,
                AccessPolicyAssignment.segment_target_key == build_segment_target_key(
                    payload.segment_id, payload.target_start_ip, payload.target_end_ip
                ),
            ]
        )

    result = await db.execute(select(AccessPolicyAssignment).where(and_(*filters)))
    return result.scalars().first()


async def validate_segment_exception(
    db: AsyncSession,
    payload: AccessPolicyAssignmentCreate,
    exclude_id: Optional[int] = None,
):
    if payload.segment_id is None:
        return

    segment_res = await db.execute(
        select(NetworkSegment).where(NetworkSegment.id == payload.segment_id)
    )
    segment = segment_res.scalars().first()
    if not segment:
        raise HTTPException(status_code=404, detail="Network segment not found")

    has_start = bool(payload.target_start_ip and payload.target_start_ip.strip())
    has_end = bool(payload.target_end_ip and payload.target_end_ip.strip())

    if has_start and has_end:
        try:
            start_ip = ipaddress.ip_address(payload.target_start_ip)
            end_ip = ipaddress.ip_address(payload.target_end_ip)
        except ValueError:
             raise HTTPException(status_code=422, detail="Invalid IPv4 format in exception range")
            
        segment_net = ipaddress.ip_network(segment.cidr, strict=False)

        if start_ip not in segment_net or end_ip not in segment_net:
            raise HTTPException(
                status_code=422,
                detail="Exception IPs must strictly fall within the parent NetworkSegment CIDR",
            )

        stmt = select(AccessPolicyAssignment).where(
            and_(
                AccessPolicyAssignment.username == payload.username,
                AccessPolicyAssignment.segment_id == payload.segment_id,
                AccessPolicyAssignment.target_start_ip.is_not(None),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(AccessPolicyAssignment.id != exclude_id)

        existing_res = await db.execute(stmt)
        existing = existing_res.scalars().all()

        for exc in existing:
            if not exc.target_start_ip or not exc.target_end_ip:
                continue
            try:
                exc_start = ipaddress.ip_address(exc.target_start_ip)
                exc_end = ipaddress.ip_address(exc.target_end_ip)
                if start_ip <= exc_end and end_ip >= exc_start:
                    raise HTTPException(
                        status_code=422,
                        detail=f"IP range overlaps with existing exception: {exc.target_start_ip} - {exc.target_end_ip}",
                    )
            except ValueError:
                continue
        return

    stmt = select(AccessPolicyAssignment).where(
        and_(
            AccessPolicyAssignment.username == payload.username,
            AccessPolicyAssignment.segment_id == payload.segment_id,
            AccessPolicyAssignment.target_start_ip.is_(None),
            AccessPolicyAssignment.target_end_ip.is_(None),
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(AccessPolicyAssignment.id != exclude_id)

    existing_base_res = await db.execute(stmt)
    existing_base = existing_base_res.scalars().first()
    if existing_base:
        raise HTTPException(
            status_code=409,
            detail="A base policy for this user and network segment already exists",
        )


def to_out_schema(record: AccessPolicyAssignment) -> AccessPolicyAssignmentOut:
    """Serialize AccessPolicyAssignment ORM → Out schema, resolving related names."""
    days = compute_days_until_review(record.review_date)
    
    # Resolve category and segment names from relationships if available
    category_name = None
    if record.nas_category_id is not None:
        try:
            category_name = record.category.name if record.category else None
        except Exception:
            category_name = None
            
    segment_name = None
    if record.segment_id is not None:
        try:
            segment_name = record.segment.name if record.segment else None
        except Exception:
            segment_name = None

    return AccessPolicyAssignmentOut(
        id=record.id,
        username=record.username,
        nas_ip=record.nas_ip,
        calling_station_id=record.calling_station_id,
        nas_category_id=record.nas_category_id,
        nas_category_name=category_name,
        nas_identifier=record.nas_identifier,
        nas_vendor=record.nas_vendor,
        radius_group=record.radius_group,
        privilege_level=record.privilege_level,
        justification=record.justification,
        approved_by=record.approved_by,
        review_date=record.review_date.date() if record.review_date else None,
        is_active=record.is_active,
        created_at=record.created_at,
        updated_at=record.updated_at,
        days_until_review=days,
        segment_id=record.segment_id,
        segment_name=segment_name,
        target_start_ip=record.target_start_ip,
        target_end_ip=record.target_end_ip,
    )
