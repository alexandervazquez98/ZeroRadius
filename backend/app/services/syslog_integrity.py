"""
Syslog Integrity Service — ISO 27001 A.5.33 (Chain of Custody)
Computes and verifies SHA-256 hash chain for syslog_events records.
"""

import hashlib
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

logger = logging.getLogger(__name__)

GENESIS_HASH = hashlib.sha256(b"ZERO").hexdigest()


def compute_syslog_hash(
    previous_hash: str, received_at: str, device_ip: str, program: str, message: str
) -> str:
    """
    Compute a deterministic SHA-256 hash for a syslog event.
    Hash = SHA256(previous_hash + received_at + device_ip + program + message)
    """
    payload = f"{previous_hash}{received_at}{device_ip}{program or ''}{message}"
    return hashlib.sha256(payload.encode()).hexdigest()


async def backfill_syslog_hashes(db: AsyncSession, batch_size: int = 500) -> int:
    """
    Fill previous_hash and hash for syslog_events where hash is NULL.
    Processes records sequentially ordered by received_at, id.
    First record gets genesis hash as previous_hash.
    Returns the count of records updated.
    """
    from app.models.models import SyslogEvent

    updated_count = 0
    last_hash = GENESIS_HASH

    while True:
        result = await db.execute(
            select(SyslogEvent)
            .where(SyslogEvent.hash.is_(None))
            .order_by(SyslogEvent.received_at.asc(), SyslogEvent.id.asc())
            .limit(batch_size)
        )
        records = result.scalars().all()

        if not records:
            break

        for record in records:
            received_at_str = (
                record.received_at.isoformat() if record.received_at else ""
            )
            program_str = record.program or ""

            new_hash = compute_syslog_hash(
                last_hash,
                received_at_str,
                record.device_ip,
                program_str,
                record.message,
            )

            record.previous_hash = last_hash
            record.hash = new_hash
            last_hash = new_hash

        await db.commit()
        updated_count += len(records)
        logger.info("SyslogIntegrityService: backfilled %d records", len(records))

        if len(records) < batch_size:
            break

    return updated_count


async def verify_syslog_record(db: AsyncSession, record_id: int) -> bool:
    """
    Verify that a stored syslog_event's hash matches the computed hash.
    Returns True if the record is intact, False if tampering is detected or hash is missing.
    """
    from app.models.models import SyslogEvent

    result = await db.execute(select(SyslogEvent).where(SyslogEvent.id == record_id))
    record = result.scalars().first()

    if not record:
        return False

    if not record.hash or not record.previous_hash:
        return False

    received_at_str = record.received_at.isoformat() if record.received_at else ""
    program_str = record.program or ""

    computed = compute_syslog_hash(
        record.previous_hash,
        received_at_str,
        record.device_ip,
        program_str,
        record.message,
    )

    return computed == record.hash
