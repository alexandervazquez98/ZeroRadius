"""
Schema validation for runtime database drift detection.

This module provides runtime validation that the actual database schema matches
the SQLAlchemy model definitions. It uses SQLAlchemy Inspector to reflect the
live database and compares it against Base.metadata.

Used during FastAPI startup to fail fast if schema drift is detected.

Error format from spec:
- Which table/column is affected
- Whether the issue is a missing column, extra column, or type mismatch
- Recommended remediation steps
"""

from collections.abc import AsyncIterator
from typing import Final

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.exceptions import KNOWN_EXCEPTIONS
from app.db.session import Base


def _get_model_columns() -> dict[str, set[str]]:
    """Introspect SQLAlchemy Base.metadata and return {table_name: {col1, col2, ...}}.

    Returns:
        dict mapping table names to sets of column names from the ORM models.
    """
    tables: dict[str, set[str]] = {}
    for table in Base.metadata.sorted_tables:
        table_name = table.name.lower()
        columns = {col.name.lower() for col in table.columns}
        tables[table_name] = columns
    return tables


def _format_drift_error(table_name: str, column_name: str | None = None) -> str:
    """Format a schema drift error message with table/column info and remediation.

    Args:
        table_name: The name of the affected table.
        column_name: The name of the affected column, if applicable.

    Returns:
        A formatted error message with diagnostic info and remediation steps.
    """
    if column_name:
        return (
            f"Schema drift detected: table '{table_name}' is missing column '{column_name}'. "
            f"→ Add the column to the database schema or add '{column_name}' to KNOWN_EXCEPTIONS "
            f"if the column is intentionally ORM-only."
        )
    else:
        return (
            f"Schema drift detected: table '{table_name}' is missing from the database. "
            f"→ Create the table in the database or run Alembic migrations."
        )


async def validate_schema_drift(
    engine: AsyncEngine,
    known_exceptions: dict[str, set[str]] | None = None,
) -> list[str]:
    """Compare actual DB columns vs SQLAlchemy models.

    Uses SQLAlchemy Inspector to reflect the live database and compares it
    against Base.metadata. Returns a list of drift error messages (empty = valid).

    Args:
        engine: The AsyncEngine to use for database inspection.
        known_exceptions: Optional dict of {table_name: {column_names}} to ignore.
                         Defaults to KNOWN_EXCEPTIONS from app.db.exceptions.

    Returns:
        List of drift error messages. Empty list means schema is valid.

    Raises:
        RuntimeError: If database connection fails.
    """
    if known_exceptions is None:
        known_exceptions = KNOWN_EXCEPTIONS

    errors: list[str] = []

    # Get model columns from SQLAlchemy
    model_columns = _get_model_columns()

    # Reflect actual DB columns using Inspector
    try:
        async with engine.begin() as conn:
            db_columns: dict[str, set[str]] = {}
            db_table_names: set[str] = set()

            # Get all table names
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            db_table_names = {t.lower() for t in table_names}

            # Get columns for each table
            for table_name in db_table_names:
                columns = await conn.run_sync(
                    lambda sync_conn, t=table_name: {
                        col["name"].lower()
                        for col in inspect(sync_conn).get_columns(t)
                    }
                )
                db_columns[table_name.lower()] = columns

    except Exception as exc:
        raise RuntimeError(f"Failed to connect to database for schema validation: {exc}") from exc

    # Check for missing tables (model has table but DB doesn't)
    model_tables = set(model_columns.keys())
    missing_tables = model_tables - db_table_names
    for table in sorted(missing_tables):
        errors.append(_format_drift_error(table))

    # Check for missing columns
    for table_name in sorted(model_columns.keys()):
        if table_name not in db_table_names:
            # Already reported as missing table
            continue

        model_cols = model_columns[table_name]
        db_cols = db_columns.get(table_name, set())
        exceptions = known_exceptions.get(table_name, set())

        # Find columns in model but not in DB (excluding known exceptions)
        missing_cols = model_cols - db_cols - exceptions
        for col in sorted(missing_cols):
            errors.append(_format_drift_error(table_name, col))

    return errors


def validate_schema_drift_sync(
    engine: Engine,
    known_exceptions: dict[str, set[str]] | None = None,
) -> list[str]:
    """Synchronous version of validate_schema_drift for use in non-async contexts.

    Uses the sync engine to perform inspection.
    """
    if known_exceptions is None:
        known_exceptions = KNOWN_EXCEPTIONS

    errors: list[str] = []

    # Get model columns from SQLAlchemy
    model_columns = _get_model_columns()

    # Reflect actual DB columns using Inspector (synchronous)
    try:
        inspector = inspect(engine)
        db_columns: dict[str, set[str]] = {}
        db_table_names: set[str] = set()

        # Get all table names
        table_names = inspector.get_table_names()
        db_table_names = {t.lower() for t in table_names}

        # Get columns for each table
        for table_name in db_table_names:
            columns = inspector.get_columns(table_name)
            db_columns[table_name.lower()] = {col["name"].lower() for col in columns}

    except Exception as exc:
        raise RuntimeError(f"Failed to connect to database for schema validation: {exc}") from exc

    # Check for missing tables (model has table but DB doesn't)
    model_tables = set(model_columns.keys())
    missing_tables = model_tables - db_table_names
    for table in sorted(missing_tables):
        errors.append(_format_drift_error(table))

    # Check for missing columns
    for table_name in sorted(model_columns.keys()):
        if table_name not in db_table_names:
            # Already reported as missing table
            continue

        model_cols = model_columns[table_name]
        db_cols = db_columns.get(table_name, set())
        exceptions = known_exceptions.get(table_name, set())

        # Find columns in model but not in DB (excluding known exceptions)
        missing_cols = model_cols - db_cols - exceptions
        for col in sorted(missing_cols):
            errors.append(_format_drift_error(table_name, col))

    return errors
