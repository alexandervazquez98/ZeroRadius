"""
Unit tests: syslog_events monthly partition maintenance.

The backend test DB is SQLite (no partitioning), so the planner is tested as a
pure function and the executor against a recording fake MySQL session.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.services.syslog_partitions import (
    maintain_syslog_partitions,
    plan_partition_changes,
)

INIT_SQL_PARTITIONS = [
    "p202604",
    "p202605",
    "p202606",
    "p202607",
    "p202608",
    "p202609",
    "p202610",
    "p202611",
    "p202612",
    "pmax",
]


class TestPlanPartitionChanges:
    def test_creates_months_ahead_beyond_last_partition(self):
        plan = plan_partition_changes(
            INIT_SQL_PARTITIONS, date(2026, 11, 23), retention_months=3, months_ahead=3
        )
        # Nov 2026 + 3 months ahead = up to Feb 2027; p202612 already exists.
        assert plan.to_add == [("p202701", 202702), ("p202702", 202703)]

    def test_drops_partitions_older_than_retention(self):
        plan = plan_partition_changes(
            INIT_SQL_PARTITIONS, date(2026, 11, 23), retention_months=3, months_ahead=3
        )
        # Keep current month + 3 previous full months (Aug..Nov).
        assert plan.to_drop == ["p202604", "p202605", "p202606", "p202607"]

    def test_year_boundary_bounds(self):
        plan = plan_partition_changes(
            ["p202611", "pmax"], date(2026, 12, 1), retention_months=3, months_ahead=1
        )
        assert plan.to_add == [("p202612", 202701), ("p202701", 202702)]
        assert plan.to_drop == []

    def test_no_changes_when_up_to_date(self):
        plan = plan_partition_changes(
            ["p202608", "p202609", "p202610", "p202611", "p202612", "p202701", "p202702", "pmax"],
            date(2026, 11, 23),
            retention_months=3,
            months_ahead=3,
        )
        assert plan.to_add == []
        assert plan.to_drop == []

    def test_never_drops_current_month(self):
        plan = plan_partition_changes(
            ["p202610", "p202611", "pmax"], date(2026, 11, 5), retention_months=0, months_ahead=0
        )
        assert "p202611" not in plan.to_drop
        assert plan.to_drop == ["p202610"]

    def test_ignores_unknown_partition_names(self):
        plan = plan_partition_changes(
            ["legacy", "p20261", "pmax", "p202611"], date(2026, 11, 5), retention_months=3, months_ahead=0
        )
        assert plan.to_drop == []
        assert plan.to_add == []


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeSession:
    """Records executed SQL; answers the information_schema partition query."""

    def __init__(self, dialect, partitions):
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect))
        self._partitions = partitions
        self.statements: list[str] = []
        self.commits = 0

    def get_bind(self):
        return self._bind

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "information_schema.PARTITIONS" in sql:
            return _Result([(p,) for p in self._partitions])
        self.statements.append(" ".join(sql.split()))
        return _Result([])

    async def commit(self):
        self.commits += 1


class TestMaintainSyslogPartitions:
    @pytest.mark.asyncio
    async def test_reorganizes_pmax_and_drops_expired(self):
        db = _FakeSession("mysql", INIT_SQL_PARTITIONS)
        plan = await maintain_syslog_partitions(
            db, today=date(2026, 11, 23), retention_months=3, months_ahead=3
        )
        assert plan is not None
        assert db.statements == [
            (
                "ALTER TABLE syslog_events REORGANIZE PARTITION pmax INTO ("
                "PARTITION p202701 VALUES LESS THAN (202702), "
                "PARTITION p202702 VALUES LESS THAN (202703), "
                "PARTITION pmax VALUES LESS THAN MAXVALUE)"
            ),
            "ALTER TABLE syslog_events DROP PARTITION p202604, p202605, p202606, p202607",
        ]

    @pytest.mark.asyncio
    async def test_adds_partitions_when_no_pmax(self):
        db = _FakeSession("mariadb", ["p202611"])
        await maintain_syslog_partitions(
            db, today=date(2026, 11, 23), retention_months=3, months_ahead=1
        )
        assert db.statements == [
            (
                "ALTER TABLE syslog_events ADD PARTITION ("
                "PARTITION p202612 VALUES LESS THAN (202701))"
            ),
        ]

    @pytest.mark.asyncio
    async def test_skips_non_partitioned_table(self):
        db = _FakeSession("mysql", [])
        plan = await maintain_syslog_partitions(db, today=date(2026, 11, 23))
        assert plan is None
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_skips_non_mysql_dialect(self):
        db = _FakeSession("sqlite", INIT_SQL_PARTITIONS)
        plan = await maintain_syslog_partitions(db, today=date(2026, 11, 23))
        assert plan is None
        assert db.statements == []

    @pytest.mark.asyncio
    async def test_retention_and_lookahead_from_env(self, monkeypatch):
        monkeypatch.setenv("SYSLOG_RETENTION_MONTHS", "6")
        monkeypatch.setenv("SYSLOG_PARTITIONS_AHEAD", "1")
        db = _FakeSession("mysql", INIT_SQL_PARTITIONS)
        plan = await maintain_syslog_partitions(db, today=date(2026, 11, 23))
        assert plan.to_add == []
        assert plan.to_drop == ["p202604"]
