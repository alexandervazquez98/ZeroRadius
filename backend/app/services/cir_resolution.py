from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import Nas, UserNasPrivilegeMap
from app.routers.privilege_map import _to_out
from app.schemas.schemas import (
    CIRPreviewResponse,
    CIRResolutionTraceItem,
)
from app.services.cir_profiles import get_profile


@dataclass
class _Candidate:
    path: str
    mapping: UserNasPrivilegeMap


def _ip_in_range(ip: ipaddress.IPv4Address, start: str, end: str) -> bool:
    return ipaddress.ip_address(start) <= ip <= ipaddress.ip_address(end)


async def _resolve_exact_or_range(
    db: AsyncSession, username: str, nas_ip: ipaddress.IPv4Address
) -> _Candidate | None:
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(
            selectinload(UserNasPrivilegeMap.category),
            selectinload(UserNasPrivilegeMap.segment),
        )
        .where(
            and_(
                UserNasPrivilegeMap.username == username,
                UserNasPrivilegeMap.is_active == 1,
            )
        )
    )
    rows = result.scalars().all()

    exact = [r for r in rows if r.nas_ip and ipaddress.ip_address(r.nas_ip) == nas_ip]
    if exact:
        exact_sorted = sorted(exact, key=lambda r: r.id)
        return _Candidate(path="exact", mapping=exact_sorted[0])

    ranged = [
        r
        for r in rows
        if r.segment_id
        and r.target_start_ip
        and r.target_end_ip
        and _ip_in_range(nas_ip, r.target_start_ip, r.target_end_ip)
    ]
    if ranged:
        ranged_sorted = sorted(
            ranged,
            key=lambda r: (
                int(ipaddress.ip_address(r.target_end_ip))
                - int(ipaddress.ip_address(r.target_start_ip)),
                r.id,
            ),
        )
        return _Candidate(path="range", mapping=ranged_sorted[0])

    return None


async def _resolve_segment(
    db: AsyncSession, username: str, nas_ip: ipaddress.IPv4Address
) -> _Candidate | None:
    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(selectinload(UserNasPrivilegeMap.segment))
        .where(
            and_(
                UserNasPrivilegeMap.username == username,
                UserNasPrivilegeMap.is_active == 1,
                UserNasPrivilegeMap.segment_id.is_not(None),
                UserNasPrivilegeMap.target_start_ip.is_(None),
                UserNasPrivilegeMap.target_end_ip.is_(None),
            )
        )
    )
    rows = result.scalars().all()
    matching: list[tuple[int, UserNasPrivilegeMap]] = []
    for row in rows:
        if not row.segment:
            continue
        segment = ipaddress.ip_network(row.segment.cidr, strict=False)
        if nas_ip in segment:
            matching.append((segment.prefixlen, row))

    if not matching:
        return None

    matching.sort(key=lambda item: (-item[0], item[1].id))
    return _Candidate(path="segment", mapping=matching[0][1])


async def _resolve_nas_category(db: AsyncSession, nas_ip: ipaddress.IPv4Address) -> int | None:
    result = await db.execute(select(Nas).where(Nas.category_id.is_not(None)))
    rows = result.scalars().all()

    candidates: list[tuple[int, int]] = []
    for row in rows:
        try:
            ip = ipaddress.ip_address(row.nasname)
            if ip == nas_ip:
                candidates.append((32, row.category_id))
                continue
        except ValueError:
            pass

        try:
            network = ipaddress.ip_network(row.nasname, strict=False)
            if nas_ip in network:
                candidates.append((network.prefixlen, row.category_id))
        except ValueError:
            continue

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


async def _resolve_category(
    db: AsyncSession, username: str, nas_ip: ipaddress.IPv4Address
) -> _Candidate | None:
    category_id = await _resolve_nas_category(db, nas_ip)
    if category_id is None:
        return None

    result = await db.execute(
        select(UserNasPrivilegeMap)
        .options(selectinload(UserNasPrivilegeMap.category))
        .where(
            and_(
                UserNasPrivilegeMap.username == username,
                UserNasPrivilegeMap.is_active == 1,
                UserNasPrivilegeMap.nas_category_id == category_id,
                UserNasPrivilegeMap.nas_ip.is_(None),
                UserNasPrivilegeMap.segment_id.is_(None),
            )
        )
    )
    row = result.scalars().first()
    if row:
        return _Candidate(path="category", mapping=row)
    return None


async def resolve_preview(
    db: AsyncSession, username: str, nas_ip: str
) -> CIRPreviewResponse:
    ip = ipaddress.ip_address(nas_ip)
    trace: list[CIRResolutionTraceItem] = []

    exact_or_range = await _resolve_exact_or_range(db, username, ip)
    if exact_or_range:
        profile = await get_profile(db, exact_or_range.mapping.radius_group)
        trace.append(
            CIRResolutionTraceItem(
                step="exact_or_range",
                matched=True,
                detail=f"matched {exact_or_range.path}",
            )
        )
        trace.append(
            CIRResolutionTraceItem(
                step="segment",
                matched=False,
                detail="skipped due higher-precedence match",
            )
        )
        trace.append(
            CIRResolutionTraceItem(
                step="category",
                matched=False,
                detail="skipped due higher-precedence match",
            )
        )
        return CIRPreviewResponse(
            resolution_path=exact_or_range.path,
            mapping=_to_out(exact_or_range.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(CIRResolutionTraceItem(step="exact_or_range", matched=False))

    segment = await _resolve_segment(db, username, ip)
    if segment:
        profile = await get_profile(db, segment.mapping.radius_group)
        trace.append(CIRResolutionTraceItem(step="segment", matched=True))
        return CIRPreviewResponse(
            resolution_path="segment",
            mapping=_to_out(segment.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(CIRResolutionTraceItem(step="segment", matched=False))

    category = await _resolve_category(db, username, ip)
    if category:
        profile = await get_profile(db, category.mapping.radius_group)
        trace.append(CIRResolutionTraceItem(step="category", matched=True))
        return CIRPreviewResponse(
            resolution_path="category",
            mapping=_to_out(category.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(CIRResolutionTraceItem(step="category", matched=False))

    return CIRPreviewResponse(
        resolution_path="none",
        mapping=None,
        profile=None,
        trace=trace,
    )
