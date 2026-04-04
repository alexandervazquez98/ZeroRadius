"""
PrivilegeMap router — ISO 27001 A.5.15, A.8.2
CRUD for user-NAS privilege mappings with RBAC and audit trail.
Supports both IP-based and category-based targeting (nas-categories feature).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, date
from starlette.requests import Request
from app.db.session import get_db
from app.models.models import UserNasPrivilegeMap, AdminUser
from app.schemas.schemas import (
    UserNasPrivilegeMapCreate,
    UserNasPrivilegeMapBulkCreate,
    UserNasPrivilegeMapOut,
)
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
from app.services.audit import log_audit, EventCode

router = APIRouter(prefix="/privilege-map", tags=["privilege-map"])


def _compute_days_until_review(review_date: Optional[datetime]) -> Optional[int]:
    """Compute days until review. Negative means overdue."""
    if review_date is None:
        return None
    today = datetime.utcnow().date()
    delta = review_date.date() - today
    return delta.days


def _to_out(record: UserNasPrivilegeMap) -> UserNasPrivilegeMapOut:
    """Serialize UserNasPrivilegeMap ORM → Out schema, resolving category name."""
    days = _compute_days_until_review(record.review_date)
    # Resolve category name if relationship is loaded
    category_name = None
    if record.nas_category_id is not None:
        try:
            category_name = record.category.name if record.category else None
        except Exception:
            category_name = None
    return UserNasPrivilegeMapOut(
        id=record.id,
        username=record.username,
        nas_ip=record.nas_ip,
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
    )


@router.get("", response_model=list[UserNasPrivilegeMapOut])
@limiter.limit("60/minute")
async def list_privilege_maps(
    request: Request,
    username: Optional[str] = None,
    nas_ip: Optional[str] = None,
    is_active: Optional[int] = None,
    overdue_review: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    """
    List privilege mappings. Supports filtering by username, nas_ip, is_active, overdue_review.
    Returns both IP-based and category-based entries.
    Accessible by auditor, admin, and superadmin.
    """
    from app.models.models import NasCategory

    stmt = select(UserNasPrivilegeMap).options(
        selectinload(UserNasPrivilegeMap.category)
    )
    filters = []

    if username:
        filters.append(UserNasPrivilegeMap.username == username)
    if nas_ip:
        filters.append(UserNasPrivilegeMap.nas_ip == nas_ip)
    if is_active is not None:
        filters.append(UserNasPrivilegeMap.is_active == is_active)
    if overdue_review:
        filters.append(UserNasPrivilegeMap.review_date < datetime.utcnow())

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_to_out(r) for r in records]


@router.post("", response_model=list[UserNasPrivilegeMapOut], status_code=201)
@limiter.limit("30/minute")
async def create_privilege_map_bulk(
    request: Request,
    payload: UserNasPrivilegeMapBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Create privilege mapping(s) in bulk — IP-based only.
    For category-based entries use POST /privilege-map/category.
    Requires admin or superadmin role.
    """
    review_dt = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )

    records = []
    for ip in payload.nas_ips:
        record = UserNasPrivilegeMap(
            username=payload.username,
            nas_ip=ip,
            nas_category_id=None,
            nas_identifier=payload.nas_identifier,
            nas_vendor=payload.nas_vendor,
            radius_group=payload.radius_group,
            privilege_level=payload.privilege_level,
            justification=payload.justification,
            approved_by=payload.approved_by,
            review_date=review_dt,
            is_active=payload.is_active,
        )
        db.add(record)
        records.append(record)

    await db.commit()
    for record in records:
        await db.refresh(record)

    await log_audit(
        db,
        current_user.username,
        "CREATE_BULK",
        "user_nas_privilege_map",
        payload.username,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return [_to_out(r) for r in records]


@router.post("/category", response_model=UserNasPrivilegeMapOut, status_code=201)
@limiter.limit("30/minute")
async def create_privilege_map_category(
    request: Request,
    payload: UserNasPrivilegeMapCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Create a single privilege mapping targeting a NAS category (not a specific IP).
    Requires admin or superadmin role.
    """
    if payload.nas_category_id is None:
        raise HTTPException(
            status_code=422,
            detail="nas_category_id is required for category-based entries",
        )

    review_dt = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )

    record = UserNasPrivilegeMap(
        username=payload.username,
        nas_ip=None,
        nas_category_id=payload.nas_category_id,
        nas_identifier=payload.nas_identifier,
        nas_vendor=payload.nas_vendor,
        radius_group=payload.radius_group,
        privilege_level=payload.privilege_level,
        justification=payload.justification,
        approved_by=payload.approved_by,
        review_date=review_dt,
        is_active=payload.is_active,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    # Load category relationship for the response
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(selectinload(UserNasPrivilegeMap.category))
        .where(UserNasPrivilegeMap.id == record.id)
    )
    record = result.scalars().first()

    await log_audit(
        db,
        current_user.username,
        "CREATE_CATEGORY",
        "user_nas_privilege_map",
        payload.username,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return _to_out(record)


@router.put("/{id}", response_model=UserNasPrivilegeMapOut)
@limiter.limit("30/minute")
async def update_privilege_map(
    request: Request,
    id: int,
    payload: UserNasPrivilegeMapCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Update an existing privilege mapping (IP-based or category-based).
    Requires admin or superadmin role.
    """
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(selectinload(UserNasPrivilegeMap.category))
        .where(UserNasPrivilegeMap.id == id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Privilege map entry not found")

    old_out = _to_out(record)

    review_dt = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )

    record.username = payload.username
    record.nas_ip = payload.nas_ip
    record.nas_category_id = payload.nas_category_id
    record.nas_identifier = payload.nas_identifier
    record.nas_vendor = payload.nas_vendor
    record.radius_group = payload.radius_group
    record.privilege_level = payload.privilege_level
    record.justification = payload.justification
    record.approved_by = payload.approved_by
    record.review_date = review_dt
    record.is_active = payload.is_active
    record.updated_at = datetime.utcnow()

    await db.commit()

    # Reload with relationship for response
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(selectinload(UserNasPrivilegeMap.category))
        .where(UserNasPrivilegeMap.id == id)
    )
    record = result.scalars().first()

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "user_nas_privilege_map",
        payload.username,
        old_value=old_out.model_dump(mode="json"),
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return _to_out(record)


@router.delete("/{id}")
@limiter.limit("30/minute")
async def delete_privilege_map(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    """
    Delete a privilege mapping.
    Requires superadmin role.
    """
    result = await db.execute(
        select(UserNasPrivilegeMap).where(UserNasPrivilegeMap.id == id)
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Privilege map entry not found")

    old_out = _to_out(record)
    await db.delete(record)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "user_nas_privilege_map",
        record.username,
        old_value=old_out.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return {"ok": True}
