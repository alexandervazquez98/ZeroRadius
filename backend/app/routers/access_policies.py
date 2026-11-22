from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.limiter import limiter
from app.core.rbac import Role, require_roles
from app.db.session import get_db
from app.models.models import AdminUser, AccessPolicyAssignment, RadGroupCheck, RadGroupReply
from app.schemas.access_policies import (
    AccessPolicyAssignmentOut,
    AccessPolicyAssignmentCreate,
    AccessPolicyAssignmentBulkCreate,
    AccessPolicyAssignmentBulkUpdate,
    AccessPolicyAssignmentBulkDelete,
    AccessPolicyPreviewRequest,
    AccessPolicyPreviewResponse,
    BandwidthProfileOut,
    BandwidthProfilePayload,
)
from app.services.access_policies_service import (
    ensure_single_active_in_category,
    find_existing_assignment,
    raise_assignment_integrity_error,
    raise_nas_conflict,
    to_out_schema as _to_out,
    validate_category_membership,
    validate_segment_exception,
)
from app.services.bandwidth_profiles import (
    delete_profile,
    list_profiles,
    upsert_profile,
    resolve_preview,
)
from app.services.audit import log_audit, EventCode


router = APIRouter(prefix="/access-policies", tags=["access-policies"])


@router.get("/bandwidth-profiles", response_model=list[BandwidthProfileOut])
@limiter.limit("60/minute")
async def get_bandwidth_profiles(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),       
):
    return await list_profiles(db)


@router.post("/bandwidth-profiles", response_model=BandwidthProfileOut, status_code=201)
@limiter.limit("30/minute")
async def create_bandwidth_profile(
    request: Request,
    payload: BandwidthProfilePayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    return await upsert_profile(db, payload)


@router.put("/bandwidth-profiles/{profile_name}", response_model=BandwidthProfileOut)
@limiter.limit("30/minute")
async def update_bandwidth_profile(
    request: Request,
    profile_name: str,
    payload: BandwidthProfilePayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    if payload.name.strip() != profile_name.strip():
        raise HTTPException(status_code=422, detail="profile name mismatch")
    return await upsert_profile(db, payload)


@router.delete("/bandwidth-profiles/{profile_name}")
@limiter.limit("30/minute")
async def remove_bandwidth_profile(
    request: Request,
    profile_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    removed = await delete_profile(db, profile_name)
    if not removed:
        raise HTTPException(status_code=404, detail="Bandwidth profile not found")
    return {"ok": True}


@router.get("/assignments", response_model=list[AccessPolicyAssignmentOut])
@limiter.limit("60/minute")
async def list_assignments(
    request: Request,
    username: Optional[str] = None,
    nas_ip: Optional[str] = None,
    is_active: Optional[int] = None,
    overdue_review: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    stmt = select(AccessPolicyAssignment).options(
        selectinload(AccessPolicyAssignment.category),
        selectinload(AccessPolicyAssignment.segment),
    )
    filters = []

    if username:
        filters.append(AccessPolicyAssignment.username == username)
    if nas_ip:
        filters.append(AccessPolicyAssignment.nas_ip == nas_ip)
    if is_active is not None:
        filters.append(AccessPolicyAssignment.is_active == is_active)
    if overdue_review:
        filters.append(AccessPolicyAssignment.review_date < datetime.utcnow())

    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    records = result.scalars().all()
    return [_to_out(r) for r in records]


@router.post("/assignments", response_model=AccessPolicyAssignmentOut, status_code=201)
@limiter.limit("120/minute")
async def create_or_replace_assignment(
    request: Request,
    payload: AccessPolicyAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    await validate_category_membership(
        db,
        payload.username,
        payload.nas_category_id,
        payload.calling_station_id,
    )

    existing = await find_existing_assignment(db, payload)

    await validate_segment_exception(
        db, payload, exclude_id=existing.id if existing else None
    )

    review_dt = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )

    if existing:
        existing.username = payload.username
        existing.nas_ip = payload.nas_ip
        existing.calling_station_id = payload.calling_station_id
        existing.nas_category_id = payload.nas_category_id
        existing.segment_id = payload.segment_id
        existing.target_start_ip = payload.target_start_ip
        existing.target_end_ip = payload.target_end_ip
        existing.nas_identifier = payload.nas_identifier
        existing.nas_vendor = payload.nas_vendor
        existing.radius_group = payload.radius_group
        existing.privilege_level = payload.privilege_level
        existing.justification = payload.justification
        existing.approved_by = payload.approved_by
        existing.review_date = review_dt
        existing.is_active = payload.is_active
        existing.cir_id = payload.cir_id
        existing.updated_at = datetime.utcnow()
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise_assignment_integrity_error(payload, exc)
        
        result = await db.execute(
            select(AccessPolicyAssignment)
            .options(
                selectinload(AccessPolicyAssignment.category),
                selectinload(AccessPolicyAssignment.segment),
            )
            .where(AccessPolicyAssignment.id == existing.id)
        )
        return _to_out(result.scalars().first())

    row = AccessPolicyAssignment(
        username=payload.username,
        nas_ip=payload.nas_ip,
        calling_station_id=payload.calling_station_id,
        nas_category_id=payload.nas_category_id,
        segment_id=payload.segment_id,
        target_start_ip=payload.target_start_ip,
        target_end_ip=payload.target_end_ip,
        nas_identifier=payload.nas_identifier,
        nas_vendor=payload.nas_vendor,
        radius_group=payload.radius_group,
        privilege_level=payload.privilege_level,
        justification=payload.justification,
        approved_by=payload.approved_by,
        review_date=review_dt,
        is_active=payload.is_active,
        cir_id=payload.cir_id,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise_assignment_integrity_error(payload, exc)
    await db.refresh(row)

    result = await db.execute(
        select(AccessPolicyAssignment)
        .options(
            selectinload(AccessPolicyAssignment.category),
            selectinload(AccessPolicyAssignment.segment),
        )
        .where(AccessPolicyAssignment.id == row.id)
    )
    
    await log_audit(
        db,
        current_user.username,
        "CREATE_SINGLE",
        "access_policy_assignments",
        payload.username,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return _to_out(result.scalars().first())


@router.post("/assignments/bulk", response_model=list[AccessPolicyAssignmentOut], status_code=201)
@limiter.limit("120/minute")
async def create_assignments_bulk(
    request: Request,
    payload: AccessPolicyAssignmentBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    review_dt = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )

    records = []
    for ip in payload.nas_ips:
        record = AccessPolicyAssignment(
            username=payload.username,
            nas_ip=ip,
            nas_category_id=None,
            segment_id=None,
            target_start_ip=None,
            target_end_ip=None,
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

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        dummy = AccessPolicyAssignmentCreate(
            username=payload.username,
            nas_ip=payload.nas_ips[0],
            radius_group=payload.radius_group
        )
        raise_nas_conflict(dummy)

    for record in records:
        await db.refresh(record)

    await log_audit(
        db,
        current_user.username,
        "CREATE_BULK",
        "access_policy_assignments",
        payload.username,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return [_to_out(r) for r in records]


async def _load_assignments(db: AsyncSession, ids: list[int]) -> list[AccessPolicyAssignment]:
    """Load all ``ids`` (with category/segment for snapshots) or 404 listing the missing ones."""
    result = await db.execute(
        select(AccessPolicyAssignment)
        .options(
            selectinload(AccessPolicyAssignment.category),
            selectinload(AccessPolicyAssignment.segment),
        )
        .where(AccessPolicyAssignment.id.in_(ids))
    )
    rows = result.scalars().all()
    missing = sorted(set(ids) - {r.id for r in rows})
    if missing:
        raise HTTPException(status_code=404, detail=f"Access policy entries not found: {missing}")
    return rows


@router.patch("/assignments/bulk", response_model=list[AccessPolicyAssignmentOut])
@limiter.limit("30/minute")
async def bulk_update_assignments(
    request: Request,
    payload: AccessPolicyAssignmentBulkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """Change group / privilege / review date / active flag of many rows (#97).

    All-or-nothing: every row is validated before any change. Targets are not
    editable here, so target_key uniqueness cannot be violated. One audit
    entry per row, committed in the same transaction as the changes.
    """
    changes = payload.model_dump(exclude_unset=True, exclude={"ids"})

    if "radius_group" in changes:
        group = changes["radius_group"]
        known = (
            await db.execute(select(RadGroupReply.id).where(RadGroupReply.groupname == group).limit(1))
        ).first() or (
            await db.execute(select(RadGroupCheck.id).where(RadGroupCheck.groupname == group).limit(1))
        ).first()
        if not known:
            raise HTTPException(status_code=422, detail=f"RADIUS group '{group}' does not exist")

    rows = await _load_assignments(db, payload.ids)

    if changes.get("is_active") == 1:
        reactivated = [r for r in rows if r.nas_category_id is not None and not r.is_active]
        seen: set[tuple[str, int]] = set()
        for r in reactivated:
            key = (r.username, r.nas_category_id)
            if key in seen:
                raise HTTPException(
                    status_code=409,
                    detail=f"{r.username} would have two active assignments in the same category",
                )
            seen.add(key)
            await ensure_single_active_in_category(db, r.username, r.nas_category_id, exclude_id=r.id)

    now = datetime.utcnow()
    for row in rows:
        old = _to_out(row).model_dump(mode="json")
        for field, value in changes.items():
            if field == "review_date":
                value = datetime.combine(value, datetime.min.time()) if value else None
            setattr(row, field, value)
        row.updated_at = now
        new = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in changes.items()}
        await log_audit(
            db,
            current_user.username,
            "BULK_UPDATE",
            "access_policy_assignments",
            row.username,
            old_value=old,
            new_value={"id": row.id, **new},
            event_code=EventCode.ADMIN_002,
            commit=False,
        )
    await db.commit()

    return [_to_out(r) for r in await _load_assignments(db, payload.ids)]


@router.post("/assignments/bulk-delete")
@limiter.limit("30/minute")
async def bulk_delete_assignments(
    request: Request,
    payload: AccessPolicyAssignmentBulkDelete,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    """Delete many rows (superadmin only, like single delete). All-or-nothing,
    one audit entry per row in the same transaction (#97)."""
    ids = list(dict.fromkeys(payload.ids))
    rows = await _load_assignments(db, ids)
    for row in rows:
        await log_audit(
            db,
            current_user.username,
            "BULK_DELETE",
            "access_policy_assignments",
            row.username,
            old_value=_to_out(row).model_dump(mode="json"),
            event_code=EventCode.ADMIN_002,
            commit=False,
        )
        await db.delete(row)
    await db.commit()
    return {"deleted": len(rows)}


@router.put("/assignments/{assignment_id}", response_model=AccessPolicyAssignmentOut)
@limiter.limit("120/minute")
async def update_assignment(
    request: Request,
    assignment_id: int,
    payload: AccessPolicyAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    await validate_segment_exception(db, payload, exclude_id=assignment_id)

    await validate_category_membership(
        db,
        payload.username,
        payload.nas_category_id,
        payload.calling_station_id,
    )

    result = await db.execute(
        select(AccessPolicyAssignment)
        .options(
            selectinload(AccessPolicyAssignment.category),
            selectinload(AccessPolicyAssignment.segment),
        )
        .where(AccessPolicyAssignment.id == assignment_id)
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Access policy entry not found")

    old_out = _to_out(row)

    # One active assignment per user per category. Only category rows are
    # subject to it: for IP/MAC/segment rows nas_category_id is NULL, and
    # comparing NULL == NULL matched every other non-category row (#97).
    if payload.nas_category_id is not None:
        await ensure_single_active_in_category(
            db, payload.username, payload.nas_category_id, exclude_id=assignment_id
        )

    row.username = payload.username
    row.nas_ip = payload.nas_ip
    row.calling_station_id = payload.calling_station_id
    row.nas_category_id = payload.nas_category_id
    row.segment_id = payload.segment_id
    row.target_start_ip = payload.target_start_ip
    row.target_end_ip = payload.target_end_ip
    row.nas_identifier = payload.nas_identifier
    row.nas_vendor = payload.nas_vendor
    row.radius_group = payload.radius_group
    row.privilege_level = payload.privilege_level
    row.justification = payload.justification
    row.approved_by = payload.approved_by
    row.review_date = (
        datetime.combine(payload.review_date, datetime.min.time())
        if payload.review_date
        else None
    )
    row.is_active = payload.is_active
    row.cir_id = payload.cir_id
    row.updated_at = datetime.utcnow()

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise_assignment_integrity_error(payload, exc)

    await db.refresh(row)
    
    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "access_policy_assignments",
        payload.username,
        old_value=old_out.model_dump(mode="json"),
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return _to_out(row)


@router.delete("/assignments/{assignment_id}")
@limiter.limit("120/minute")
async def delete_assignment(
    request: Request,
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    result = await db.execute(
        select(AccessPolicyAssignment).where(AccessPolicyAssignment.id == assignment_id)
    )
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="Access policy entry not found")

    old_out = _to_out(row)
    await db.delete(row)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "access_policy_assignments",
        row.username,
        old_value=old_out.model_dump(mode="json"),
        event_code=EventCode.ADMIN_002,
    )
    return {"ok": True}


@router.post("/preview", response_model=AccessPolicyPreviewResponse)
@limiter.limit("60/minute")
async def preview_resolution(
    request: Request,
    payload: AccessPolicyPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    return await resolve_preview(
        db, payload.username, payload.nas_ip, calling_station_id=payload.calling_station_id
    )
