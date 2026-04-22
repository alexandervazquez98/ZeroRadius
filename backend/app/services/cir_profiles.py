from __future__ import annotations

from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import RadGroupReply
from app.schemas.schemas import CIRProfileOut, CIRProfilePayload

CIR_GROUP_PREFIX = "cir_"

# Keep this whitelist in sync with radius/policy.d/nas_based_authorization
CIR_ATTRIBUTE_MAP: dict[str, str] = {
    "downlink_high": "Cambium-Canopy-HPDLCIR",
    "uplink_high": "Cambium-Canopy-HPULCIR",
    "downlink_low": "Cambium-Canopy-LPDLCIR",
    "uplink_low": "Cambium-Canopy-LPULCIR",
}


def is_cir_group(groupname: str) -> bool:
    return groupname.startswith(CIR_GROUP_PREFIX)


async def get_profile(db: AsyncSession, groupname: str) -> CIRProfileOut | None:
    if not is_cir_group(groupname):
        return None

    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname == groupname)
    )
    rows = result.scalars().all()
    if not rows:
        return None

    data = {"groupname": groupname, "name": groupname[len(CIR_GROUP_PREFIX) :]}
    inv_map = {v: k for k, v in CIR_ATTRIBUTE_MAP.items()}
    for row in rows:
        if row.attribute in inv_map:
            data[inv_map[row.attribute]] = row.value

    # Fill missing fields
    for field in CIR_ATTRIBUTE_MAP.keys():
        if field not in data:
            data[field] = "0"

    return CIRProfileOut(**data)


async def list_profiles(db: AsyncSession) -> list[CIRProfileOut]:
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname.like(f"{CIR_GROUP_PREFIX}%"))
    )
    rows = result.scalars().all()

    # Group attributes by groupname
    by_group = defaultdict(dict)
    for row in rows:
        by_group[row.groupname][row.attribute] = row.value

    profiles = []
    for groupname, attrs in by_group.items():
        inv_map = {v: k for k, v in CIR_ATTRIBUTE_MAP.items()}
        data = {"groupname": groupname, "name": groupname[len(CIR_GROUP_PREFIX) :]}
        for attr, val in attrs.items():
            if attr in inv_map:
                data[inv_map[attr]] = val

        for field in CIR_ATTRIBUTE_MAP.keys():
            if field not in data:
                data[field] = "0"

        profiles.append(CIRProfileOut(**data))

    return profiles


async def upsert_profile(db: AsyncSession, payload: CIRProfilePayload) -> CIRProfileOut:
    groupname = f"{CIR_GROUP_PREFIX}{payload.name.strip().lower().replace(' ', '_')}"
    await db.execute(delete(RadGroupReply).where(RadGroupReply.groupname == groupname))
    for field, attr in CIR_ATTRIBUTE_MAP.items():
        val = getattr(payload, field)
        db.add(RadGroupReply(groupname=groupname, attribute=attr, op=":=", value=val))
    await db.commit()
    return CIRProfileOut(**payload.model_dump(), groupname=groupname)


async def delete_profile(db: AsyncSession, profile_name: str) -> bool:
    groupname = f"{CIR_GROUP_PREFIX}{profile_name}"
    result = await db.execute(select(RadGroupReply).where(RadGroupReply.groupname == groupname))
    if not result.scalars().first():
        return False
    await db.execute(delete(RadGroupReply).where(RadGroupReply.groupname == groupname))
    await db.commit()
    return True
