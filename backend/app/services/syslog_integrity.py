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


def _event_hash(previous_hash: str, record) -> str:
    return compute_syslog_hash(
        previous_hash,
        record.received_at.isoformat() if record.received_at else "",
        record.device_ip,
        record.program or "",
        record.message,
    )


async def _chain_tip(db: AsyncSession) -> str:
    """Hash of the last event already in the chain, or GENESIS_HASH if none."""
    from app.models.models import SyslogEvent

    result = await db.execute(
        select(SyslogEvent.hash)
        .where(SyslogEvent.hash.is_not(None))
        .order_by(SyslogEvent.id.desc())
        .limit(1)
    )
    return result.scalar() or GENESIS_HASH


async def backfill_syslog_hashes(db: AsyncSession, batch_size: int = 500) -> int:
    """
    Append events with hash IS NULL to the hash chain, in insertion (id) order.

    Each run continues from the last hashed event (#138); only the very first
    event ever hashed uses GENESIS_HASH. Insertion order, not received_at,
    defines the chain, so an event that arrives late is still appended after
    the current tip. Ingest is a single sequential writer (the syslog
    forwarder), so ids are committed in increasing order.
    Returns the count of records updated.
    """
    from app.models.models import SyslogEvent

    updated_count = 0
    last_hash = await _chain_tip(db)

    while True:
        result = await db.execute(
            select(SyslogEvent)
            .where(SyslogEvent.hash.is_(None))
            .order_by(SyslogEvent.id.asc())
            .limit(batch_size)
        )
        records = result.scalars().all()

        if not records:
            break

        for record in records:
            record.previous_hash = last_hash
            record.hash = _event_hash(last_hash, record)
            last_hash = record.hash

        await db.commit()
        updated_count += len(records)
        logger.debug("SyslogIntegrityService: backfilled %d records", len(records))

        if len(records) < batch_size:
            break

    return updated_count


async def verify_syslog_chain(
    db: AsyncSession, since_id: Optional[int] = None, batch_size: int = 1000
) -> dict:
    """
    Walk hashed events in id order and report the first break in the chain.

    Checks that each event's hash matches its content and that its
    previous_hash equals the prior event's hash. The first event checked is
    only checked against its own content: retention drops old partitions, so
    the oldest surviving event need not point at GENESIS_HASH. Pass
    `since_id` to start after a known cut-over (events hashed before #138
    restart the chain about once a minute).
    """
    from app.models.models import SyslogEvent

    checked = 0
    prev_hash = None
    after_id = (since_id - 1) if since_id is not None else None

    while True:
        stmt = select(SyslogEvent).where(SyslogEvent.hash.is_not(None))
        if after_id is not None:
            stmt = stmt.where(SyslogEvent.id > after_id)
        records = (
            await db.execute(stmt.order_by(SyslogEvent.id.asc()).limit(batch_size))
        ).scalars().all()
        if not records:
            break

        for record in records:
            if prev_hash is not None and record.previous_hash != prev_hash:
                return {
                    "checked": checked,
                    "first_break_id": record.id,
                    "reason": "previous_hash does not match the prior event",
                }
            if record.previous_hash is None or _event_hash(record.previous_hash, record) != record.hash:
                return {"checked": checked, "first_break_id": record.id, "reason": "hash mismatch"}
            prev_hash = record.hash
            checked += 1

        after_id = records[-1].id
        db.expunge_all()  # keep memory flat on large tables

    return {"checked": checked, "first_break_id": None, "reason": None}


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
