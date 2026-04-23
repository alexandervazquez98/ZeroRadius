from datetime import datetime
import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.limiter import limiter
from app.core.rbac import Role, require_roles
from app.db.session import get_db
from app.models.models import AdminUser, UserNasPrivilegeMap, _build_segment_target_key
from app.services.privilege_map_service import (
    to_out_schema as _to_out,
    raise_nas_conflict,
    validate_segment_exception,
)
from app.schemas.schemas import (
    CIRAssignmentPayload,
    CIRPreviewRequest,
    CIRPreviewResponse,
    CIRProfileOut,
    CIRProfilePayload,
    UserNasPrivilegeMapOut,
)
from app.services.cir_profiles import (
    delete_profile,
    is_cir_group,
    list_profiles,
    upsert_profile,
)
from app.services.cir_resolution import resolve_preview

router = APIRouter(prefix="/cir", tags=["cir"])


def _is_unique_integrity_error(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)

    # Prefer structured driver metadata first (SQLSTATE/errno) instead of
    # brittle message parsing.
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


def _raise_assignment_integrity_error(
    payload: CIRAssignmentPayload, exc: IntegrityError
) -> None:
    if _is_unique_integrity_error(exc):
        raise_nas_conflict(payload)

    raise HTTPException(
        status_code=422,
        detail="CIR assignment violates data integrity constraints",
    ) from exc


@router.get("/profiles", response_model=list[CIRProfileOut])
@limiter.limit("60/minute")
async def get_cir_profiles(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),       
):
    return await list_profiles(db)


@router.post("/profiles", response_model=CIRProfileOut, status_code=201)
@limiter.limit("30/minute")
async def create_cir_profile(
    request: Request,
    payload: CIRProfilePayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    return await upsert_profile(db, payload)


@router.put("/profiles/{profile_name}", response_model=CIRProfileOut)
@limiter.limit("30/minute")
async def update_cir_profile(
    request: Request,
    profile_name: str,
    payload: CIRProfilePayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    if payload.name.strip().lower().replace(" ", "_") != profile_name.strip().lower().replace(
        " ", "_"
    ):
        raise HTTPException(status_code=422, detail="profile name mismatch")
    return await upsert_profile(db, payload)


@router.delete("/profiles/{profile_name}")
@limiter.limit("30/minute")
async def remove_cir_profile(
    request: Request,
    profile_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    removed = await delete_profile(db, profile_name)
    if not removed:
        raise HTTPException(status_code=404, detail="CIR profile not found")
    return {"ok": True}


async def _find_existing_assignment(
    db: AsyncSession,
    payload: CIRAssignmentPayload,
) -> UserNasPrivilegeMap | None:
    filters = [UserNasPrivilegeMap.username == payload.username]

    if payload.calling_station_id and payload.nas_ip:
        filters.extend(
            [
                UserNasPrivilegeMap.calling_station_id == payload.calling_station_id,
                UserNasPrivilegeMap.nas_ip == payload.nas_ip,
            ]
        )
    elif payload.calling_station_id:
        filters.extend(
            [
                UserNasPrivilegeMap.calling_station_id == payload.calling_station_id,
                UserNasPrivilegeMap.nas_ip.is_(None),
            ]
        )
    elif payload.nas_ip:
        filters.extend(
            [
                UserNasPrivilegeMap.nas_ip == payload.nas_ip,
                UserNasPrivilegeMap.calling_station_id.is_(None),
                UserNasPrivilegeMap.segment_id.is_(None),
                UserNasPrivilegeMap.nas_category_id.is_(None),
            ]
        )
    elif payload.nas_category_id is not None:
        filters.extend(
            [
                UserNasPrivilegeMap.nas_category_id == payload.nas_category_id,
                UserNasPrivilegeMap.nas_ip.is_(None),
                UserNasPrivilegeMap.segment_id.is_(None),
            ]
        )
    else:
        filters.extend(
            [
                UserNasPrivilegeMap.segment_id == payload.segment_id,
                UserNasPrivilegeMap.segment_target_key == _build_segment_target_key(
                    payload.segment_id, payload.target_start_ip, payload.target_end_ip
                ),
            ]
        )

    result = await db.execute(select(UserNasPrivilegeMap).where(and_(*filters)))
    return result.scalars().first()


@router.get("/assignments", response_model=list[UserNasPrivilegeMapOut])
@limiter.limit("60/minute")
async def list_cir_assignments(
    request: Request,
    username: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    stmt = select(UserNasPrivilegeMap).options(
        selectinload(UserNasPrivilegeMap.category),
        selectinload(UserNasPrivilegeMap.segment),
    )
    filters = [UserNasPrivilegeMap.radius_group.like("cir_%")]
    if username:
        filters.append(UserNasPrivilegeMap.username == username)
    stmt = stmt.where(and_(*filters))
    result = await db.execute(stmt)
    return [_to_out(row) for row in result.scalars().all()]


@router.post("/assignments", response_model=UserNasPrivilegeMapOut, status_code=201)
@limiter.limit("30/minute")
async def create_or_replace_cir_assignment(
    request: Request,
    payload: CIRAssignmentPayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    existing = await _find_existing_assignment(db, payload)

    # Prevent collision with non-CIR groups
    if existing and not is_cir_group(existing.radius_group):
        raise_nas_conflict(payload)

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
        existing.updated_at = datetime.utcnow()
        try:
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            _raise_assignment_integrity_error(payload, exc)
        # Reload relationships
        result = await db.execute(
            select(UserNasPrivilegeMap)
            .options(
                selectinload(UserNasPrivilegeMap.category),
                selectinload(UserNasPrivilegeMap.segment),
            )
            .where(UserNasPrivilegeMap.id == existing.id)
        )
        return _to_out(result.scalars().first())

    row = UserNasPrivilegeMap(
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
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        _raise_assignment_integrity_error(payload, exc)
    await db.refresh(row)

    # Reload relationships
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(
            selectinload(UserNasPrivilegeMap.category),
            selectinload(UserNasPrivilegeMap.segment),
        )
        .where(UserNasPrivilegeMap.id == row.id)
    )
    return _to_out(result.scalars().first())


@router.put("/assignments/{assignment_id}", response_model=UserNasPrivilegeMapOut)
@limiter.limit("30/minute")
async def update_cir_assignment(
    request: Request,
    assignment_id: int,
    payload: CIRAssignmentPayload,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    await validate_segment_exception(db, payload, exclude_id=assignment_id)

    result = await db.execute(
        select(UserNasPrivilegeMap).where(UserNasPrivilegeMap.id == assignment_id)
    )
    row = result.scalars().first()
    if not row or not is_cir_group(row.radius_group):
        raise HTTPException(status_code=404, detail="CIR assignment not found")

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
    row.updated_at = datetime.utcnow()

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        _raise_assignment_integrity_error(payload, exc)

    await db.refresh(row)
    return _to_out(row)


@router.delete("/assignments/{assignment_id}")
@limiter.limit("30/minute")
async def delete_cir_assignment(
    request: Request,
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    result = await db.execute(
        select(UserNasPrivilegeMap).where(UserNasPrivilegeMap.id == assignment_id)
    )
    row = result.scalars().first()
    if not row or not is_cir_group(row.radius_group):
        raise HTTPException(status_code=404, detail="CIR assignment not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.post("/preview", response_model=CIRPreviewResponse)
@limiter.limit("60/minute")
async def preview_cir_resolution(
    request: Request,
    payload: CIRPreviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    return await resolve_preview(
        db, payload.username, payload.nas_ip, calling_station_id=payload.calling_station_id
    )
