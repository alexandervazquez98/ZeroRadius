import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, select
from starlette.requests import Request
from typing import List

from app.db.session import get_db
from app.models.models import NetworkSegment, AdminUser, AccessPolicyAssignment
from app.schemas.schemas import (
    NetworkSegmentCreate,
    NetworkSegmentUpdate,
    NetworkSegmentOut,
)
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
from app.services.audit import log_audit, EventCode

router = APIRouter(prefix="/network-segments", tags=["network-segments"])


async def _get_overlapping_segment(
    db: AsyncSession, candidate_cidr: str, exclude_id: int | None = None
) -> NetworkSegment | None:
    candidate_net = ipaddress.ip_network(candidate_cidr, strict=False)
    result = await db.execute(select(NetworkSegment))

    for segment in result.scalars().all():
        if exclude_id is not None and segment.id == exclude_id:
            continue

        existing_net = ipaddress.ip_network(segment.cidr, strict=False)
        if existing_net.version == candidate_net.version and existing_net.overlaps(
            candidate_net
        ):
            return segment

    return None


async def _get_invalid_segment_exceptions(
    db: AsyncSession, segment_id: int, candidate_cidr: str
) -> list[AccessPolicyAssignment]:
    segment_net = ipaddress.ip_network(candidate_cidr, strict=False)
    result = await db.execute(
        select(AccessPolicyAssignment).where(
            and_(
                AccessPolicyAssignment.segment_id == segment_id,
                AccessPolicyAssignment.target_start_ip.is_not(None),
                AccessPolicyAssignment.target_end_ip.is_not(None),
            )
        )
    )

    invalid: list[AccessPolicyAssignment] = []
    for mapping in result.scalars().all():
        start_ip = ipaddress.ip_address(mapping.target_start_ip)
        end_ip = ipaddress.ip_address(mapping.target_end_ip)
        if start_ip not in segment_net or end_ip not in segment_net:
            invalid.append(mapping)

    return invalid


async def _ensure_segment_can_use_cidr(
    db: AsyncSession, candidate_cidr: str, exclude_id: int | None = None
):
    overlapping = await _get_overlapping_segment(db, candidate_cidr, exclude_id)
    if overlapping:
        raise HTTPException(
            status_code=409,
            detail=(
                "Network segment CIDR overlaps with existing segment "
                f"'{overlapping.name}' ({overlapping.cidr})"
            ),
        )


@router.get("", response_model=List[NetworkSegmentOut])
@limiter.limit("60/minute")
async def list_network_segments(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.AUDITOR, Role.ADMIN, Role.SUPERADMIN),
):
    result = await db.execute(select(NetworkSegment))
    return result.scalars().all()


@router.post("", response_model=NetworkSegmentOut, status_code=201)
@limiter.limit("30/minute")
async def create_network_segment(
    request: Request,
    payload: NetworkSegmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    # Check if name already exists
    existing = await db.execute(
        select(NetworkSegment).where(NetworkSegment.name == payload.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=400, detail="Network segment name already exists"
        )

    await _ensure_segment_can_use_cidr(db, payload.cidr)

    record = NetworkSegment(
        name=payload.name, cidr=payload.cidr, description=payload.description
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "network_segments",
        payload.name,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_009,
    )
    return record


@router.put("/{id}", response_model=NetworkSegmentOut)
@limiter.limit("30/minute")
async def update_network_segment(
    request: Request,
    id: int,
    payload: NetworkSegmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    result = await db.execute(select(NetworkSegment).where(NetworkSegment.id == id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Network segment not found")

    old_data = {
        "name": record.name,
        "cidr": record.cidr,
        "description": record.description,
    }

    if payload.name is not None and payload.name != record.name:
        existing = await db.execute(
            select(NetworkSegment).where(NetworkSegment.name == payload.name)
        )
        if existing.scalars().first():
            raise HTTPException(
                status_code=400, detail="Network segment name already exists"
            )
        record.name = payload.name

    if payload.cidr is not None:
        try:
            ipaddress.ip_network(payload.cidr, strict=False)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="cidr must be a valid IP network CIDR"
            )

        await _ensure_segment_can_use_cidr(db, payload.cidr, exclude_id=record.id)

        invalid_exceptions = await _get_invalid_segment_exceptions(
            db, record.id, payload.cidr
        )
        if invalid_exceptions:
            first_invalid = invalid_exceptions[0]
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cannot update network segment CIDR because dependent exception "
                    f"{first_invalid.target_start_ip}-{first_invalid.target_end_ip} "
                    "would fall outside the segment"
                ),
            )

        record.cidr = payload.cidr

    if payload.description is not None:
        record.description = payload.description

    await db.commit()
    await db.refresh(record)

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "network_segments",
        record.name,
        old_value=old_data,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_009,
    )
    return record


@router.delete("/{id}")
@limiter.limit("30/minute")
async def delete_network_segment(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    result = await db.execute(select(NetworkSegment).where(NetworkSegment.id == id))
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Network segment not found")

    old_data = {
        "name": record.name,
        "cidr": record.cidr,
        "description": record.description,
    }

    dependent_privilege_maps = await db.execute(
        select(AccessPolicyAssignment.id).where(
            AccessPolicyAssignment.segment_id == record.id
        )
    )
    if dependent_privilege_maps.first() is not None:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete network segment while dependent privilege maps exist",
        )

    await db.delete(record)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "network_segments",
        record.name,
        old_value=old_data,
        event_code=EventCode.ADMIN_009,
    )
    return {"ok": True}
