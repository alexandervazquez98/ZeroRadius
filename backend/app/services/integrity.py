"""
IntegrityHashService — ISO 27001 A.5.33
Computes and verifies SHA-256 integrity hashes for radpostauth records.
"""

import hashlib
import json
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

# Fields used for the canonical hash of authentication records
CRITICAL_FIELDS_AUTH = [
    "username",
    "authdate",
    "nas_ip_address",
    "reply",
    "calling_station_id",
]


def compute_hash(record: dict, fields: list[str]) -> str:
    """
    Compute a deterministic SHA-256 hash for a given record dict using the specified fields.

    - Missing fields are treated as empty string (no KeyError raised)
    - Field order in record dict is irrelevant (canonical form sorts keys)
    - Returns "sha256:" + 64-char hex digest = 71 characters total
    """
    canonical = {k: str(record.get(k, "") or "") for k in sorted(fields)}
    payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


async def backfill_hashes(db: AsyncSession, batch_size: int = 500) -> int:
    """
    Fill integrity_hash for radpostauth records where it is NULL.
    Processes in batches to avoid large transactions.
    Returns the count of records updated.
    """
    from app.models.models import RadPostAuth

    updated_count = 0
    while True:
        result = await db.execute(
            select(RadPostAuth)
            .where(RadPostAuth.integrity_hash.is_(None))
            .limit(batch_size)
        )
        records = result.scalars().all()

        if not records:
            break

        for record in records:
            record_dict = {
                "username": record.username or "",
                "authdate": str(record.authdate) if record.authdate else "",
                "nas_ip_address": record.nas_ip_address or "",
                "reply": record.reply or "",
                "calling_station_id": record.calling_station_id or "",
            }
            record.integrity_hash = compute_hash(record_dict, CRITICAL_FIELDS_AUTH)

        await db.commit()
        updated_count += len(records)
        logger.info("IntegrityHashService: backfilled %d records", len(records))

        if len(records) < batch_size:
            break

    return updated_count


async def verify_record(db: AsyncSession, record_id: int) -> bool:
    """
    Verify that a stored radpostauth record's integrity_hash matches the computed hash.
    Returns True if the record is intact, False if tampering is detected or hash is missing.
    """
    from app.models.models import RadPostAuth

    result = await db.execute(select(RadPostAuth).where(RadPostAuth.id == record_id))
    record = result.scalars().first()

    if not record:
        return False

    if not record.integrity_hash:
        return False

    record_dict = {
        "username": record.username or "",
        "authdate": str(record.authdate) if record.authdate else "",
        "nas_ip_address": record.nas_ip_address or "",
        "reply": record.reply or "",
        "calling_station_id": record.calling_station_id or "",
    }
    computed = compute_hash(record_dict, CRITICAL_FIELDS_AUTH)
    return computed == record.integrity_hash
