"""syslog_events indexes for list keyset, nas-status and the hash worker

Revision ID: a1b2c3d8
Revises: f0123d7
Create Date: 2026-11-25 18:00:00.000000

One online ALTER (ALGORITHM=INPLACE, LOCK=NONE): inserts keep flowing while
the indexes build. Low-cardinality severity/facility indexes are dropped and
the single-column received_at/device_ip indexes are replaced by composites
that cover them (#136).
"""

from typing import Optional, Sequence, Union

from alembic import op
from sqlalchemy import inspect


revision: str = "a1b2c3d8"
down_revision: Union[str, None] = "f0123d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "syslog_events"

NEW_INDEXES = {
    "idx_syslog_received_id": "received_at, id",
    "idx_syslog_device_received": "device_ip, received_at",
    "idx_syslog_hash_pending": "hash(1)",
}
OLD_INDEXES = {
    "idx_syslog_received_at": "received_at",
    "idx_syslog_device_ip": "device_ip",
    "idx_syslog_severity": "severity",
    "idx_syslog_facility": "facility",
}


def _alter(existing: set, add: dict, drop: dict) -> Optional[str]:
    clauses = [f"ADD INDEX {name} ({cols})" for name, cols in add.items() if name not in existing]
    clauses += [f"DROP INDEX {name}" for name in drop if name in existing]
    if not clauses:
        return None
    return f"ALTER TABLE {TABLE} " + ", ".join(clauses) + ", ALGORITHM=INPLACE, LOCK=NONE"


def upgrade_statement(existing: set) -> Optional[str]:
    return _alter(existing, NEW_INDEXES, OLD_INDEXES)


def downgrade_statement(existing: set) -> Optional[str]:
    return _alter(existing, OLD_INDEXES, NEW_INDEXES)


def _existing_indexes() -> Optional[set]:
    bind = op.get_bind()
    if bind.dialect.name not in ("mysql", "mariadb"):
        return None  # prefix index and online ALTER are MySQL/MariaDB only
    inspector = inspect(bind)
    if TABLE not in inspector.get_table_names():
        return None
    return {i["name"] for i in inspector.get_indexes(TABLE)}


def upgrade() -> None:
    existing = _existing_indexes()
    if existing is not None and (sql := upgrade_statement(existing)):
        op.execute(sql)


def downgrade() -> None:
    existing = _existing_indexes()
    if existing is not None and (sql := downgrade_statement(existing)):
        op.execute(sql)
