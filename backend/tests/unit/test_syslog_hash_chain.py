"""Syslog hash chain continuity (#138).

backfill_syslog_hashes ran every 60 s and restarted every run from
GENESIS_HASH, so production held a new chain segment about every minute and
deleting a whole segment could not be detected. The chain must continue from
the last hashed event across runs, in insertion (id) order.

Each test uses its own empty in-memory database: the shared test DB already
holds unhashed syslog rows from other tests.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.models import SyslogEvent
from app.services.syslog_integrity import (
    GENESIS_HASH,
    backfill_syslog_hashes,
    compute_syslog_hash,
    verify_syslog_chain,
)

T0 = datetime(2026, 11, 25, 12, 0, 0)


@pytest.fixture
async def sessions():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SyslogEvent.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _insert(sessions, *rows):
    """rows: (id, seconds offset from T0)."""
    async with sessions() as db:
        for event_id, offset in rows:
            db.add(
                SyslogEvent(
                    id=event_id,
                    received_at=T0 + timedelta(seconds=offset),
                    device_ip="10.0.0.1",
                    facility=16,
                    severity=6,
                    program="test",
                    message=f"event {event_id}",
                )
            )
        await db.commit()


async def _backfill(sessions, batch_size=500):
    # A new session per run, like the background loop in main.py.
    async with sessions() as db:
        return await backfill_syslog_hashes(db, batch_size=batch_size)


async def _chain(sessions):
    async with sessions() as db:
        rows = (await db.execute(select(SyslogEvent).order_by(SyslogEvent.id))).scalars().all()
        return {r.id: r for r in rows}


async def _verify(sessions, **kw):
    async with sessions() as db:
        return await verify_syslog_chain(db, **kw)


async def test_first_run_starts_at_genesis(sessions):
    await _insert(sessions, (1, 0), (2, 1))
    assert await _backfill(sessions) == 2
    rows = await _chain(sessions)
    assert rows[1].previous_hash == GENESIS_HASH
    assert rows[2].previous_hash == rows[1].hash


async def test_next_run_continues_from_the_last_hashed_event(sessions):
    # Regression: the second run restarted at GENESIS_HASH.
    await _insert(sessions, (1, 0), (2, 1))
    await _backfill(sessions)
    await _insert(sessions, (3, 2), (4, 3))
    assert await _backfill(sessions) == 2
    rows = await _chain(sessions)
    assert rows[3].previous_hash == rows[2].hash
    assert rows[4].previous_hash == rows[3].hash


async def test_run_with_nothing_new_changes_nothing(sessions):
    await _insert(sessions, (1, 0))
    await _backfill(sessions)
    before = (await _chain(sessions))[1].hash
    assert await _backfill(sessions) == 0
    assert (await _chain(sessions))[1].hash == before


async def test_batches_within_one_run_stay_linked(sessions):
    await _insert(sessions, *[(n, n) for n in range(1, 6)])
    assert await _backfill(sessions, batch_size=2) == 5
    rows = await _chain(sessions)
    for n in range(2, 6):
        assert rows[n].previous_hash == rows[n - 1].hash


async def test_late_event_is_chained_in_insertion_order(sessions):
    # A requeued batch can carry a received_at older than events already hashed.
    await _insert(sessions, (1, 10), (2, 20))
    await _backfill(sessions)
    await _insert(sessions, (3, 5))  # older timestamp, inserted last
    await _backfill(sessions)
    rows = await _chain(sessions)
    assert rows[3].previous_hash == rows[2].hash


async def test_hash_formula_is_unchanged(sessions):
    await _insert(sessions, (1, 0))
    await _backfill(sessions)
    row = (await _chain(sessions))[1]
    assert row.hash == compute_syslog_hash(
        GENESIS_HASH, row.received_at.isoformat(), row.device_ip, row.program, row.message
    )


async def test_verify_accepts_an_intact_chain(sessions):
    await _insert(sessions, *[(n, n) for n in range(1, 5)])
    await _backfill(sessions, batch_size=2)
    report = await _verify(sessions)
    assert report == {"checked": 4, "first_break_id": None, "reason": None}


async def test_verify_detects_a_modified_message(sessions):
    await _insert(sessions, (1, 0), (2, 1), (3, 2))
    await _backfill(sessions)
    async with sessions() as db:
        await db.execute(update(SyslogEvent).where(SyslogEvent.id == 2).values(message="forged"))
        await db.commit()
    report = await _verify(sessions)
    assert report["first_break_id"] == 2
    assert report["reason"] == "hash mismatch"


async def test_verify_detects_a_deleted_event(sessions):
    await _insert(sessions, (1, 0), (2, 1), (3, 2))
    await _backfill(sessions)
    async with sessions() as db:
        await db.delete(await db.get(SyslogEvent, 2))
        await db.commit()
    report = await _verify(sessions)
    assert report["first_break_id"] == 3
    assert report["reason"] == "previous_hash does not match the prior event"


async def test_verify_since_id_skips_segments_from_before_the_fix(sessions):
    await _insert(sessions, (1, 0), (2, 1), (3, 2))
    await _backfill(sessions)
    # Simulate a pre-fix restart: event 2 was re-anchored at GENESIS.
    async with sessions() as db:
        row = await db.get(SyslogEvent, 2)
        row.previous_hash = GENESIS_HASH
        row.hash = compute_syslog_hash(
            GENESIS_HASH, row.received_at.isoformat(), row.device_ip, row.program, row.message
        )
        await db.execute(update(SyslogEvent).where(SyslogEvent.id == 3).values(
            previous_hash=row.hash,
            hash=compute_syslog_hash(row.hash, (T0 + timedelta(seconds=2)).isoformat(),
                                     "10.0.0.1", "test", "event 3"),
        ))
        await db.commit()

    assert (await _verify(sessions))["first_break_id"] == 2
    assert await _verify(sessions, since_id=2) == {"checked": 2, "first_break_id": None, "reason": None}


async def test_verify_ignores_events_not_hashed_yet(sessions):
    await _insert(sessions, (1, 0))
    await _backfill(sessions)
    await _insert(sessions, (2, 1))
    assert await _verify(sessions) == {"checked": 1, "first_break_id": None, "reason": None}
