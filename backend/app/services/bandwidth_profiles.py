from __future__ import annotations

import ipaddress
import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import and_, delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import AccessPolicyAssignment, RadGroupReply
from app.schemas.access_policies import (
    AccessPolicyPreviewResponse,
    AccessPolicyResolutionTraceItem,
    BandwidthProfileOut,
    BandwidthProfilePayload,
)
from app.services.access_policies_service import to_out_schema as _to_out

# Keep this whitelist in sync with radius/policy.d/nas_based_authorization
BANDWIDTH_ATTRIBUTE_MAP: dict[str, str] = {
    "downlink_high": "Cambium-Canopy-HPDLCIR",
    "uplink_high": "Cambium-Canopy-HPULCIR",
    "downlink_low": "Cambium-Canopy-LPDLCIR",
    "uplink_low": "Cambium-Canopy-LPULCIR",
}


async def get_profile(db: AsyncSession, groupname: str) -> BandwidthProfileOut | None:
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname == groupname)
    )
    rows = result.scalars().all()
    if not rows:
        return None

    data = {"groupname": groupname, "name": groupname}
    inv_map = {v: k for k, v in BANDWIDTH_ATTRIBUTE_MAP.items()}
    has_bandwidth_vsa = False
    
    for row in rows:
        if row.attribute in inv_map:
            data[inv_map[row.attribute]] = row.value
            has_bandwidth_vsa = True

    # Fill missing fields
    for field in BANDWIDTH_ATTRIBUTE_MAP.keys():
        if field not in data:
            data[field] = "0"

    # Only return as a profile if it has at least one of the bandwidth VSAs, 
    # OR if we explicitly want to allow returning any group as a 0-limit profile.
    # The requirement says we manage bandwidth profiles without the prefix.
    # To avoid treating EVERY single admin group as a bandwidth profile in the UI,
    # we should probably only consider it a bandwidth profile if it has the VSAs.
    if not has_bandwidth_vsa:
        return None

    return BandwidthProfileOut(**data)


async def list_profiles(db: AsyncSession) -> list[BandwidthProfileOut]:
    # Find all groups that have at least one bandwidth VSA
    vsa_names = list(BANDWIDTH_ATTRIBUTE_MAP.values())
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.attribute.in_(vsa_names))
    )
    rows = result.scalars().all()

    # Get the unique groupnames
    groupnames = {row.groupname for row in rows}

    if not groupnames:
        return []

    # Fetch all attributes for these groups to get a complete picture
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname.in_(groupnames))
    )
    all_rows = result.scalars().all()

    by_group = defaultdict(dict)
    for row in all_rows:
        by_group[row.groupname][row.attribute] = row.value

    profiles = []
    for groupname, attrs in by_group.items():
        inv_map = {v: k for k, v in BANDWIDTH_ATTRIBUTE_MAP.items()}
        data = {"groupname": groupname, "name": groupname}
        for attr, val in attrs.items():
            if attr in inv_map:
                data[inv_map[attr]] = val

        for field in BANDWIDTH_ATTRIBUTE_MAP.keys():
            if field not in data:
                data[field] = "0"

        profiles.append(BandwidthProfileOut(**data))

    return profiles


async def upsert_profile(db: AsyncSession, payload: BandwidthProfilePayload) -> BandwidthProfileOut:
    groupname = payload.name.strip()
    
    # Only delete the bandwidth attributes for this group, leaving other potential VSAs intact
    # Or actually, since it's a bandwidth profile manager, it might be safer to just delete
    # the bandwidth attributes and recreate them.
    vsa_names = list(BANDWIDTH_ATTRIBUTE_MAP.values())
    await db.execute(
        delete(RadGroupReply).where(
            and_(
                RadGroupReply.groupname == groupname,
                RadGroupReply.attribute.in_(vsa_names)
            )
        )
    )
    
    for field, attr in BANDWIDTH_ATTRIBUTE_MAP.items():
        val = getattr(payload, field)
        db.add(RadGroupReply(groupname=groupname, attribute=attr, op=":=", value=val))
        
    # We also need to ensure the group exists, but radgroupreply just ties them.
    # Usually returning the groupname is enough.
    
    # We do NOT commit here. The router or caller should commit. But wait, old cir_profiles did commit.
    # It's better to keep same semantics if the tests expect it. Let's not commit here if caller handles it.
    # But wait, `test_bandwidth_profiles.py` expects commit to be called.
    # Ah, I mocked `db.commit.assert_awaited_once()` in the test! I'll commit here.
    await db.commit()
    return BandwidthProfileOut(**payload.model_dump(), groupname=groupname)


async def delete_profile(db: AsyncSession, profile_name: str) -> bool:
    groupname = profile_name.strip()
    
    # Find if it has bandwidth VSAs
    vsa_names = list(BANDWIDTH_ATTRIBUTE_MAP.values())
    result = await db.execute(
        select(RadGroupReply).where(
            and_(
                RadGroupReply.groupname == groupname,
                RadGroupReply.attribute.in_(vsa_names)
            )
        )
    )
    if not result.scalars().first():
        return False
        
    # Delete the bandwidth VSAs
    await db.execute(
        delete(RadGroupReply).where(
            and_(
                RadGroupReply.groupname == groupname,
                RadGroupReply.attribute.in_(vsa_names)
            )
        )
    )
    await db.commit()
    return True


@dataclass
class _Candidate:
    path: str
    mapping: AccessPolicyAssignment


def _ip_in_range(ip: ipaddress.IPv4Address, start: str, end: str) -> bool:
    return ipaddress.ip_address(start) <= ip <= ipaddress.ip_address(end)


async def _resolve_exact_or_range(
    db: AsyncSession,
    username: str,
    nas_ip: ipaddress.IPv4Address,
    calling_station_id: str | None = None,
) -> _Candidate | None:
    result = await db.execute(
        select(AccessPolicyAssignment)
        .options(
            selectinload(AccessPolicyAssignment.category),
            selectinload(AccessPolicyAssignment.segment),
        )
        .where(
            and_(
                AccessPolicyAssignment.username == username,
                AccessPolicyAssignment.is_active == 1,
            )
        )
    )
    rows = result.scalars().all()

    if calling_station_id:
        mac_ip = [
            r
            for r in rows
            if r.calling_station_id == calling_station_id
            and r.nas_ip
            and ipaddress.ip_address(r.nas_ip) == nas_ip
        ]
        if mac_ip:
            return _Candidate(
                path="mac+ip", mapping=sorted(mac_ip, key=lambda r: r.id)[0]
            )

        mac_only = [
            r
            for r in rows
            if r.calling_station_id == calling_station_id and not r.nas_ip
        ]
        if mac_only:
            return _Candidate(
                path="mac", mapping=sorted(mac_only, key=lambda r: r.id)[0]
            )

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
        select(AccessPolicyAssignment)
        .options(selectinload(AccessPolicyAssignment.segment))
        .where(
            and_(
                AccessPolicyAssignment.username == username,
                AccessPolicyAssignment.is_active == 1,
                AccessPolicyAssignment.segment_id.is_not(None),
                AccessPolicyAssignment.target_start_ip.is_(None),
                AccessPolicyAssignment.target_end_ip.is_(None),
            )
        )
    )
    rows = result.scalars().all()
    matching: list[tuple[int, AccessPolicyAssignment]] = []
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
    stmt = text(
        """
        SELECT category_id FROM nas_cidr_ranges 
        WHERE :nas_ip_int BETWEEN net_start AND net_end 
        ORDER BY prefix_len DESC LIMIT 1
    """
    )
    result = await db.execute(stmt, {"nas_ip_int": int(nas_ip)})
    row = result.fetchone()
    return row[0] if row else None


async def _resolve_category(
    db: AsyncSession, username: str, nas_ip: ipaddress.IPv4Address
) -> _Candidate | None:
    category_id = await _resolve_nas_category(db, nas_ip)
    if category_id is None:
        return None

    result = await db.execute(
        select(AccessPolicyAssignment)
        .options(selectinload(AccessPolicyAssignment.category))
        .where(
            and_(
                AccessPolicyAssignment.username == username,
                AccessPolicyAssignment.is_active == 1,
                AccessPolicyAssignment.nas_category_id == category_id,
                AccessPolicyAssignment.nas_ip.is_(None),
                AccessPolicyAssignment.segment_id.is_(None),
            )
        )
    )
    row = result.scalars().first()
    if row:
        return _Candidate(path="category", mapping=row)
    return None


async def resolve_preview(
    db: AsyncSession, username: str, nas_ip: str, calling_station_id: str | None = None
) -> AccessPolicyPreviewResponse:
    ip = ipaddress.ip_address(nas_ip)
    
    clean_mac = None
    if calling_station_id:
        clean_mac = re.sub(r"[:-]", "", calling_station_id).lower()

    trace: list[AccessPolicyResolutionTraceItem] = []

    exact_or_range = await _resolve_exact_or_range(
        db, username, ip, calling_station_id=clean_mac
    )
    if exact_or_range:
        profile = await get_profile(db, exact_or_range.mapping.radius_group)
        trace.append(
            AccessPolicyResolutionTraceItem(
                step="exact_or_range",
                matched=True,
                detail=f"matched {exact_or_range.path}",
            )
        )
        trace.append(
            AccessPolicyResolutionTraceItem(
                step="segment",
                matched=False,
                detail="skipped due higher-precedence match",
            )
        )
        trace.append(
            AccessPolicyResolutionTraceItem(
                step="category",
                matched=False,
                detail="skipped due higher-precedence match",
            )
        )
        return AccessPolicyPreviewResponse(
            resolution_path=exact_or_range.path,
            mapping=_to_out(exact_or_range.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(AccessPolicyResolutionTraceItem(step="exact_or_range", matched=False))

    segment = await _resolve_segment(db, username, ip)
    if segment:
        profile = await get_profile(db, segment.mapping.radius_group)
        trace.append(AccessPolicyResolutionTraceItem(step="segment", matched=True))
        return AccessPolicyPreviewResponse(
            resolution_path="segment",
            mapping=_to_out(segment.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(AccessPolicyResolutionTraceItem(step="segment", matched=False))

    category = await _resolve_category(db, username, ip)
    if category:
        profile = await get_profile(db, category.mapping.radius_group)
        trace.append(AccessPolicyResolutionTraceItem(step="category", matched=True))
        return AccessPolicyPreviewResponse(
            resolution_path="category",
            mapping=_to_out(category.mapping),
            profile=profile,
            trace=trace,
        )
    trace.append(AccessPolicyResolutionTraceItem(step="category", matched=False))

    return AccessPolicyPreviewResponse(
        resolution_path="none",
        mapping=None,
        profile=None,
        trace=trace,
    )
