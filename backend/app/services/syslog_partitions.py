"""
Syslog partition maintenance.

`syslog_events` is RANGE-partitioned by month (YEAR*100 + MONTH, partitions
named ``pYYYYMM`` plus a catch-all ``pmax``). This service keeps partitions
created ahead of time and drops the ones older than the retention window.

Retention is table-wide: the current month plus the previous
``SYSLOG_RETENTION_MONTHS`` full months are kept (default 3).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from sqlalchemy import text

logger = logging.getLogger(__name__)

TABLE_NAME = "syslog_events"
CATCH_ALL = "pmax"
DEFAULT_RETENTION_MONTHS = 3
DEFAULT_MONTHS_AHEAD = 3

_PARTITION_RE = re.compile(r"^p(\d{4})(\d{2})$")


@dataclass
class PartitionPlan:
    to_add: list[tuple[str, int]] = field(default_factory=list)
    to_drop: list[str] = field(default_factory=list)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _month_key(year: int, month: int) -> int:
    return year * 100 + month


MAX_MONTHS_AHEAD = 24  # MySQL caps a table at 8192 partitions


def _env_int(name: str, default: int, maximum: int) -> int:
    """Read a non-negative int; invalid or negative values fall back to default.

    Falling back (not clamping to 0) matters for retention: 0 would drop
    every month but the current one.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        value = -1
    if value < 0:
        logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default
    return min(value, maximum)


def plan_partition_changes(
    existing: Sequence[str],
    today: date,
    retention_months: int = DEFAULT_RETENTION_MONTHS,
    months_ahead: int = DEFAULT_MONTHS_AHEAD,
) -> PartitionPlan:
    """Compute which monthly partitions to create and which to drop.

    Only names matching ``pYYYYMM`` are considered; others are left alone.
    New partitions are only appended above the highest existing month, since
    RANGE partitions can only be split off the catch-all partition.
    """
    retention_months = max(0, retention_months)
    months_ahead = max(0, months_ahead)

    monthly: dict[str, int] = {}
    for name in existing:
        match = _PARTITION_RE.match(name)
        if match:
            year, month = int(match.group(1)), int(match.group(2))
            if 1 <= month <= 12:
                monthly[name] = _month_key(year, month)

    plan = PartitionPlan()

    cutoff = _month_key(*_shift_month(today.year, today.month, -retention_months))
    plan.to_drop = sorted(name for name, key in monthly.items() if key < cutoff)

    highest = max(monthly.values(), default=0)
    for offset in range(months_ahead + 1):
        year, month = _shift_month(today.year, today.month, offset)
        key = _month_key(year, month)
        if key > highest:
            upper = _month_key(*_shift_month(year, month, 1))
            plan.to_add.append((f"p{key}", upper))

    return plan


async def _existing_partitions(db) -> list[str]:
    result = await db.execute(
        text(
            "SELECT PARTITION_NAME FROM information_schema.PARTITIONS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table "
            "AND PARTITION_NAME IS NOT NULL "
            "ORDER BY PARTITION_ORDINAL_POSITION"
        ),
        {"table": TABLE_NAME},
    )
    return [row[0] for row in result.fetchall()]


async def maintain_syslog_partitions(
    db,
    today: Optional[date] = None,
    retention_months: Optional[int] = None,
    months_ahead: Optional[int] = None,
) -> Optional[PartitionPlan]:
    """Create upcoming monthly partitions and drop expired ones.

    Returns the applied plan, or ``None`` when the database is not MySQL/MariaDB
    or ``syslog_events`` is not partitioned (nothing is changed then).
    """
    dialect = db.get_bind().dialect.name
    if dialect not in ("mysql", "mariadb"):
        return None

    existing = await _existing_partitions(db)
    if not existing:
        logger.warning(
            "%s is not partitioned; skipping partition maintenance and retention.",
            TABLE_NAME,
        )
        return None

    if retention_months is None:
        retention_months = _env_int(
            "SYSLOG_RETENTION_MONTHS", DEFAULT_RETENTION_MONTHS, maximum=1200
        )
    if months_ahead is None:
        months_ahead = _env_int(
            "SYSLOG_PARTITIONS_AHEAD", DEFAULT_MONTHS_AHEAD, maximum=MAX_MONTHS_AHEAD
        )

    plan = plan_partition_changes(
        existing, today or date.today(), retention_months, months_ahead
    )

    # Partition names come from the planner (pYYYYMM), never from user input.
    if plan.to_add:
        definitions = ", ".join(
            f"PARTITION {name} VALUES LESS THAN ({upper})" for name, upper in plan.to_add
        )
        if CATCH_ALL in existing:
            sql = (
                f"ALTER TABLE {TABLE_NAME} REORGANIZE PARTITION {CATCH_ALL} INTO "
                f"({definitions}, PARTITION {CATCH_ALL} VALUES LESS THAN MAXVALUE)"
            )
        else:
            sql = f"ALTER TABLE {TABLE_NAME} ADD PARTITION ({definitions})"
        await db.execute(text(sql))
        logger.info("Created syslog partitions: %s", [n for n, _ in plan.to_add])

    if plan.to_drop:
        await db.execute(
            text(f"ALTER TABLE {TABLE_NAME} DROP PARTITION {', '.join(plan.to_drop)}")
        )
        logger.info(
            "Dropped expired syslog partitions (retention %d months): %s",
            retention_months,
            plan.to_drop,
        )

    await db.commit()
    return plan
