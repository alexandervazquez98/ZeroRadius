from __future__ import annotations

from datetime import datetime
import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.limiter import limiter
from app.core.rbac import Role, require_roles
from app.db.session import get_db
from app.models.models import AdminUser, UserNasPrivilegeMap
from app.routers.privilege_map import (
    _to_out,
    raise_nas_conflict,
    validate_segment_exception,
)
from app.schemas.schemas import (
    UserNasPrivilegeMapOut,
    UserNasPrivilegeMapCreate,
)
from app.services.cir_profiles import (
    delete_profile,
    is_cir_group,
    list_profiles,
    upsert_profile,
)
from app.services.cir_resolution import resolve_preview

# Schemas defined directly here to break Pydantic 2.x circular resolution hell
_CIR_RATE_PATTERN = re.compile(r"^\d+$")

class CIRProfilePayload(BaseModel):
    name: str
    downlink_high: str
    uplink_high: str
    downlink_low: str
    uplink_low: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("downlink_high", "uplink_high", "downlink_low", "uplink_low", mode="before")
    @classmethod
    def validate_rate(cls, v: str) -> str:
        value = str(v or "").strip()
        if not value:
            raise ValueError("rate value is required")
        if not _CIR_RATE_PATTERN.match(value):
            raise ValueError("rate must be numeric")
        return value

class CIRProfileOut(CIRProfilePayload):
    groupname: str
    model_config = ConfigDict(from_attributes=True)

class CIRAssignmentPayload(UserNasPrivilegeMapCreate):
    @field_validator("radius_group")
    @classmethod
    def validate_radius_group(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("radius_group is required")
        if not value.startswith("cir_"):
            raise ValueError("radius_group must start with cir_")
        return value

class CIRPreviewRequest(BaseModel):
    username: str
    nas_ip: str
    calling_station_id: Optional[str] = None

class CIRResolutionTraceItem(BaseModel):
    step: str
    matched: bool
    detail: Optional[str] = None

class CIRPreviewResponse(BaseModel):
    resolution_path: str
    mapping: Optional[UserNasPrivilegeMapOut] = None
    profile: Optional[CIRProfileOut] = None
    trace: list[CIRResolutionTraceItem]

router = APIRouter(prefix="/cir", tags=["cir"])


def _segment_target_key(payload: CIRAssignmentPayload) -> str:
    if payload.segment_id is None:
        return ""
    if payload.target_start_ip is None and payload.target_end_ip is None:
        return "__base__"
    return f"{payload.target_start_ip or ''}|{payload.target_end_ip or ''}"


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
                UserNasPrivilegeMap.segment_target_key == _segment_target_key(payload),       
            ]
        )

    result = await db.execute(select(UserNasPrivilegeMap).where(and_(*filters)))
    row = result.scalars().first()
    if row and is_cir_group(row.radius_group):
        return row
    return None


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
        await db.commit()
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
    except IntegrityError:
        await db.rollback()
        raise_nas_conflict(payload)
    await db.refresh(row)

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
    except IntegrityError:
        await db.rollback()
        raise_nas_conflict(payload)

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
    # keep explicit conversion for predictable ValueError path in service
    try:
        ipaddress.ip_address(payload.nas_ip)
    except ValueError:
        raise HTTPException(status_code=422, detail="nas_ip must be a valid IPv4 address")    
    return await resolve_preview(
        db, payload.username, payload.nas_ip, calling_station_id=payload.calling_station_id   
    )
