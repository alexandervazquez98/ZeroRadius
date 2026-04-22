from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import RadGroupReply
from app.schemas.cir_schemas import CIRProfileOut, CIRProfilePayload

CIR_GROUP_PREFIX = "cir_"

# Keep this whitelist in sync with radius/policy.d/nas_based_authorization
CIR_ATTRIBUTE_MAP: dict[str, str] = {
    "downlink_high": "Cambium-Canopy-HPDLCIR",
    "uplink_high": "Cambium-Canopy-HPULCIR",
    "downlink_low": "Cambium-Canopy-LPDLCIR",
    "uplink_low": "Cambium-Canopy-LPULCIR",
}

_REVERSE_ATTRIBUTE_MAP = {v: k for k, v in CIR_ATTRIBUTE_MAP.items()}


def normalize_profile_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def to_groupname(profile_name: str) -> str:
    normalized = normalize_profile_name(profile_name)
    return (
        normalized
        if normalized.startswith(CIR_GROUP_PREFIX)
        else f"{CIR_GROUP_PREFIX}{normalized}"
    )


def profile_name_from_group(groupname: str) -> str:
    if groupname.startswith(CIR_GROUP_PREFIX):
        return groupname[len(CIR_GROUP_PREFIX) :]
    return groupname


def is_cir_group(groupname: str | None) -> bool:
    return bool(groupname and groupname.startswith(CIR_GROUP_PREFIX))


def _rows_to_profile(groupname: str, rows: Iterable[RadGroupReply]) -> CIRProfileOut | None:
    values: dict[str, str] = {}
    for row in rows:
        field_name = _REVERSE_ATTRIBUTE_MAP.get(row.attribute)
        if field_name:
            values[field_name] = row.value

    required = set(CIR_ATTRIBUTE_MAP.keys())
    if not required.issubset(values.keys()):
        return None

    return CIRProfileOut(
        name=profile_name_from_group(groupname),
        groupname=groupname,
        **values,
    )


async def list_profiles(db: AsyncSession) -> list[CIRProfileOut]:
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname.like(f"{CIR_GROUP_PREFIX}%"))
    )
    rows = result.scalars().all()

    grouped: dict[str, list[RadGroupReply]] = defaultdict(list)
    for row in rows:
        grouped[row.groupname].append(row)

    profiles: list[CIRProfileOut] = []
    for groupname in sorted(grouped.keys()):
        profile = _rows_to_profile(groupname, grouped[groupname])
        if profile:
            profiles.append(profile)
    return profiles


async def get_profile(db: AsyncSession, profile_name: str) -> CIRProfileOut | None:
    groupname = to_groupname(profile_name)
    result = await db.execute(
        select(RadGroupReply).where(RadGroupReply.groupname == groupname)
    )
    rows = result.scalars().all()
    if not rows:
        return None
    return _rows_to_profile(groupname, rows)


async def upsert_profile(db: AsyncSession, payload: CIRProfilePayload) -> CIRProfileOut:
    groupname = to_groupname(payload.name)

    await db.execute(delete(RadGroupReply).where(RadGroupReply.groupname == groupname))
    for field_name, attribute in CIR_ATTRIBUTE_MAP.items():
        db.add(
            RadGroupReply(
                groupname=groupname,
                attribute=attribute,
                op=":=",
                value=getattr(payload, field_name),
            )
        )
    await db.commit()

    return CIRProfileOut(groupname=groupname, name=profile_name_from_group(groupname), **payload.model_dump(exclude={"name"}))


async def delete_profile(db: AsyncSession, profile_name: str) -> bool:
    groupname = to_groupname(profile_name)
    result = await db.execute(
        select(RadGroupReply.id).where(RadGroupReply.groupname == groupname)
    )
    existing = result.scalars().first()
    if not existing:
        return False

    await db.execute(delete(RadGroupReply).where(RadGroupReply.groupname == groupname))
    await db.commit()
    return True
