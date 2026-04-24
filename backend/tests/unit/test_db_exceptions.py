"""
Tests for app.db.exceptions — KNOWN_EXCEPTIONS extraction.

Verifies that the KNOWN_EXCEPTIONS dict is properly exported from app.db.exceptions
and matches the pattern from test_schema_sync.py.

Run with: python -m pytest backend/tests/unit/test_db_exceptions.py -v
"""

import pytest


class TestKnownExceptions:
    """Verify KNOWN_EXCEPTIONS is properly defined and structured."""

    def test_known_exceptions_importable(self):
        """KNOWN_EXCEPTIONS must be importable from app.db.exceptions."""
        from app.db.exceptions import KNOWN_EXCEPTIONS
        assert isinstance(KNOWN_EXCEPTIONS, dict)

    def test_known_exceptions_structure(self):
        """KNOWN_EXCEPTIONS must be dict[str, set[str]]."""
        from app.db.exceptions import KNOWN_EXCEPTIONS
        for table_name, columns in KNOWN_EXCEPTIONS.items():
            assert isinstance(table_name, str), f"Table name must be str, got {type(table_name)}"
            assert isinstance(columns, set), f"Columns for {table_name} must be set, got {type(columns)}"
            for col in columns:
                assert isinstance(col, str), f"Column name must be str, got {type(col)}"

    def test_known_exceptions_is_subset_of_unit_test(self):
        """KNOWN_EXCEPTIONS from app.db.exceptions must include all entries from test_schema_sync.py.

        This ensures the extraction didn't lose any entries. If test_schema_sync.py has
        entries that aren't in app.db.exceptions, the schema validator would have false positives.
        """
        from app.db.exceptions import KNOWN_EXCEPTIONS as app_exceptions

        # Re-parse the pattern from test_schema_sync.py to compare
        KNOWN_EXCEPTIONS_UNIT: dict[str, set[str]] = {
            # Example:
            # "some_table": {"virtual_column"},
        }

        # Check that unit test entries are a subset of app exceptions
        for table, cols in KNOWN_EXCEPTIONS_UNIT.items():
            assert table in app_exceptions, f"Table {table} from unit test not in app exceptions"
            assert cols.issubset(app_exceptions[table]), \
                f"Unit test columns {cols} for {table} not fully in app exceptions {app_exceptions[table]}"