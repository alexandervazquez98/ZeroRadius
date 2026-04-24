"""
Schema sync test — Ensures init.sql stays in sync with SQLAlchemy models.

Prevents the "Unknown column" class of bugs where a developer adds a column
to a model but forgets to update init.sql.  Since ZeroRadius has no Alembic,
init.sql IS the migration system — it must define every table and column
that the ORM expects.

This test:
  1. Introspects all SQLAlchemy model classes via Base.metadata.
  2. Parses database/init.sql to extract CREATE TABLE definitions.
  3. Compares tables and columns — fails with a clear diff if anything
     is present in the models but missing from init.sql.

Run with:  python -m pytest tests/unit/test_schema_sync.py -v
"""

import re
from pathlib import Path

import pytest

from app.db.session import Base
from app.db.exceptions import KNOWN_EXCEPTIONS

# Force model registration — importing models triggers mapper config
import app.models.models  # noqa: F401


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_init_sql() -> dict[str, set[str]]:
    """
    Parse database/init.sql and return a dict of {table_name: {col1, col2, ...}}.

    Uses regex to extract CREATE TABLE blocks and their column definitions.
    Ignores KEY/INDEX/CONSTRAINT/PRIMARY KEY/UNIQUE lines.
    """
    init_sql_path = Path(__file__).resolve().parents[2] / ".." / "database" / "init.sql"
    if not init_sql_path.exists():
        pytest.fail(f"init.sql not found at {init_sql_path}")

    content = init_sql_path.read_text(encoding="utf-8")

    tables: dict[str, set[str]] = {}

    # Match CREATE TABLE blocks
    create_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\)\s*(?:ENGINE\s*=\s*\w+)?\s*;",
        re.IGNORECASE | re.DOTALL,
    )

    # Lines to skip inside CREATE TABLE (not column definitions)
    skip_re = re.compile(
        r"^\s*(?:PRIMARY\s+KEY|KEY\s|INDEX\s|UNIQUE\s|CONSTRAINT\s|FOREIGN\s+KEY)",
        re.IGNORECASE,
    )

    for match in create_re.finditer(content):
        table_name = match.group(1).lower()
        body = match.group(2)

        columns: set[str] = set()
        for line in body.split("\n"):
            line = line.strip().rstrip(",")
            if not line or skip_re.match(line):
                continue

            # First token is the column name (may be backtick-quoted)
            col_match = re.match(r"`?(\w+)`?\s+", line)
            if col_match:
                columns.add(col_match.group(1).lower())

        if columns:
            tables[table_name] = columns

    return tables


def _get_model_tables() -> dict[str, set[str]]:
    """
    Introspect SQLAlchemy Base.metadata and return {table_name: {col1, col2, ...}}.
    """
    tables: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        table_name = table.name.lower()
        columns = {col.name.lower() for col in table.columns}
        tables[table_name] = columns
    return tables


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSchemaSync:
    """Structural tests to catch model ↔ init.sql drift."""

    @pytest.fixture(scope="class")
    def sql_tables(self) -> dict[str, set[str]]:
        return _parse_init_sql()

    @pytest.fixture(scope="class")
    def model_tables(self) -> dict[str, set[str]]:
        return _get_model_tables()

    def test_all_model_tables_exist_in_init_sql(
        self, model_tables: dict, sql_tables: dict
    ):
        """Every table defined in SQLAlchemy models must have a CREATE TABLE in init.sql."""
        missing_tables = set(model_tables.keys()) - set(sql_tables.keys())

        if missing_tables:
            msg = (
                "Tables defined in SQLAlchemy models but MISSING from database/init.sql:\n"
            )
            for t in sorted(missing_tables):
                cols = ", ".join(sorted(model_tables[t]))
                msg += f"  - {t} (columns: {cols})\n"
            msg += (
                "\n→ Add the CREATE TABLE statement to database/init.sql "
                "so fresh deployments include this table."
            )
            pytest.fail(msg)

    def test_all_model_columns_exist_in_init_sql(
        self, model_tables: dict, sql_tables: dict
    ):
        """Every column in SQLAlchemy models must exist in the corresponding init.sql CREATE TABLE."""
        missing: list[str] = []

        for table_name, model_cols in model_tables.items():
            if table_name not in sql_tables:
                # Already caught by test_all_model_tables_exist_in_init_sql
                continue

            sql_cols = sql_tables[table_name]
            exceptions = KNOWN_EXCEPTIONS.get(table_name, set())
            diff = model_cols - sql_cols - exceptions

            for col in sorted(diff):
                missing.append(f"  - {table_name}.{col}")

        if missing:
            msg = (
                "Columns defined in SQLAlchemy models but MISSING from database/init.sql:\n"
                + "\n".join(missing)
                + "\n\n→ Add the missing columns to the CREATE TABLE in database/init.sql.\n"
                "→ If the column is intentionally ORM-only, add it to KNOWN_EXCEPTIONS "
                "in this test file with a comment explaining why."
            )
            pytest.fail(msg)

    def test_init_sql_is_parseable(self, sql_tables: dict):
        """Sanity check: init.sql must define at least the core RADIUS tables."""
        core_tables = {"radcheck", "radreply", "radusergroup", "nas", "radacct"}
        missing = core_tables - set(sql_tables.keys())
        assert not missing, f"Core RADIUS tables missing from init.sql parse: {missing}"

    def test_regression_device_registry_name_column_synced(self, model_tables: dict, sql_tables: dict):
        """Regression: device_registry.name must exist in both model and init.sql."""
        assert "device_registry" in model_tables
        assert "device_registry" in sql_tables
        assert "name" in model_tables["device_registry"]
        assert "name" in sql_tables["device_registry"]
