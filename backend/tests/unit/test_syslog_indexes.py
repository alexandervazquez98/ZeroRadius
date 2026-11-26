"""syslog_events indexes that keep queries off full scans (#136).

Measured in production at 1.7M rows: the hash worker (hash IS NULL ORDER BY
received_at, id) and nas-status (GROUP BY device_ip) each took ~26-29 s.
"""

import importlib.util
from pathlib import Path

from app.models.models import SyslogEvent

_ROOT = Path(__file__).resolve().parents[2]
_INIT_SQL = _ROOT.parent / "database" / "init.sql"
_MIGRATION = _ROOT / "alembic" / "versions" / "a1b2c3d8_syslog_query_indexes.py"

EXPECTED = {
    "idx_syslog_received_id": ("received_at", "id"),
    "idx_syslog_device_received": ("device_ip", "received_at"),
    "idx_syslog_hash_pending": ("hash",),
}
REMOVED = (
    "idx_syslog_received_at",
    "idx_syslog_device_ip",
    "idx_syslog_severity",
    "idx_syslog_facility",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("syslog_query_indexes", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_model_declares_query_indexes():
    indexes = {i.name: tuple(c.name for c in i.columns) for i in SyslogEvent.__table__.indexes}
    assert indexes == EXPECTED


def test_hash_index_is_a_one_char_prefix_on_mysql():
    index = next(i for i in SyslogEvent.__table__.indexes if i.name == "idx_syslog_hash_pending")
    assert index.dialect_options["mysql"]["length"] == {"hash": 1}


def test_init_sql_matches_model_indexes():
    sql = _INIT_SQL.read_text()
    assert "CREATE INDEX idx_syslog_received_id ON syslog_events(received_at, id);" in sql
    assert "CREATE INDEX idx_syslog_device_received ON syslog_events(device_ip, received_at);" in sql
    assert "CREATE INDEX idx_syslog_hash_pending ON syslog_events(hash(1));" in sql
    for name in REMOVED:
        assert name not in sql


def test_migration_follows_current_head():
    m = _load_migration()
    assert m.down_revision == "f0123d7"


def test_upgrade_is_one_online_alter_from_the_old_indexes():
    m = _load_migration()
    sql = m.upgrade_statement(set(REMOVED) | {"PRIMARY"})
    assert sql == (
        "ALTER TABLE syslog_events "
        "ADD INDEX idx_syslog_received_id (received_at, id), "
        "ADD INDEX idx_syslog_device_received (device_ip, received_at), "
        "ADD INDEX idx_syslog_hash_pending (hash(1)), "
        "DROP INDEX idx_syslog_received_at, "
        "DROP INDEX idx_syslog_device_ip, "
        "DROP INDEX idx_syslog_severity, "
        "DROP INDEX idx_syslog_facility, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )


def test_upgrade_is_idempotent():
    m = _load_migration()
    assert m.upgrade_statement(set(EXPECTED) | {"PRIMARY"}) is None


def test_downgrade_restores_the_old_indexes():
    m = _load_migration()
    sql = m.downgrade_statement(set(EXPECTED) | {"PRIMARY"})
    assert sql == (
        "ALTER TABLE syslog_events "
        "ADD INDEX idx_syslog_received_at (received_at), "
        "ADD INDEX idx_syslog_device_ip (device_ip), "
        "ADD INDEX idx_syslog_severity (severity), "
        "ADD INDEX idx_syslog_facility (facility), "
        "DROP INDEX idx_syslog_received_id, "
        "DROP INDEX idx_syslog_device_received, "
        "DROP INDEX idx_syslog_hash_pending, "
        "ALGORITHM=INPLACE, LOCK=NONE"
    )
