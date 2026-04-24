"""
Tests for app.db.schema_validator — runtime schema drift detection.

Verifies that validate_schema_drift() correctly detects columns that exist
in SQLAlchemy models but are missing from the actual database.

Run with: python -m pytest tests/unit/test_schema_validator.py -v
"""

from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine


class TestFormatDriftError:
    """Unit tests for _format_drift_error helper."""

    def test_format_drift_error_with_column_name(self):
        """_format_drift_error formats error with table and column name."""
        from app.db.schema_validator import _format_drift_error

        result = _format_drift_error("users", "email")
        assert "users" in result
        assert "email" in result
        assert "missing" in result.lower()

    def test_format_drift_error_without_column_name(self):
        """_format_drift_error formats error for missing table."""
        from app.db.schema_validator import _format_drift_error

        result = _format_drift_error("orders")
        assert "orders" in result
        assert "table" in result.lower()
        assert "missing" in result.lower()

    def test_format_drift_error_includes_remediation(self):
        """_format_drift_error includes recommended remediation steps."""
        from app.db.schema_validator import _format_drift_error

        result = _format_drift_error("users", "email")
        assert any(
            keyword in result.lower()
            for keyword in ["add", "known_exceptions", "run alembic"]
        )


class TestGetModelColumns:
    """Unit tests for _get_model_columns helper."""

    def test_get_model_columns_returns_dict(self):
        """_get_model_columns returns a dict."""
        from app.db.schema_validator import _get_model_columns

        result = _get_model_columns()
        assert isinstance(result, dict)

    def test_get_model_columns_keys_are_strings(self):
        """_get_model_columns keys are table name strings."""
        from app.db.schema_validator import _get_model_columns

        result = _get_model_columns()
        for key in result.keys():
            assert isinstance(key, str)

    def test_get_model_columns_values_are_sets(self):
        """_get_model_columns values are sets of column names."""
        from app.db.schema_validator import _get_model_columns

        result = _get_model_columns()
        for value in result.values():
            assert isinstance(value, set)
            for item in value:
                assert isinstance(item, str)


class TestValidateSchemaDriftSync:
    """Unit tests for validate_schema_drift_sync using patched sqlalchemy.inspect."""

    def test_validate_schema_drift_sync_no_drift(self):
        """validate_schema_drift_sync returns empty list when schema matches."""
        from app.db.schema_validator import validate_schema_drift_sync

        # Create a mock inspector that returns proper data
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users", "orders"]
        mock_inspector.get_columns.side_effect = lambda t: [
            {"name": "id"},
            {"name": "name"},
        ] if t == "users" else [{"name": "id"}]

        # Mock engine
        mock_engine = MagicMock()

        # Patch inspect in the schema_validator module where it's imported
        with patch("app.db.schema_validator.inspect", return_value=mock_inspector):
            # Patch _get_model_columns to return model columns matching DB
            with patch("app.db.schema_validator._get_model_columns") as mock_get_model:
                mock_get_model.return_value = {
                    "users": {"id", "name"},
                    "orders": {"id"},
                }

                from app.db.exceptions import KNOWN_EXCEPTIONS
                result = validate_schema_drift_sync(mock_engine, KNOWN_EXCEPTIONS)
                assert result == [], f"Expected no drift, got: {result}"

    def test_validate_schema_drift_sync_detects_missing_column(self):
        """validate_schema_drift_sync detects when model has column missing from DB."""
        from app.db.schema_validator import validate_schema_drift_sync

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users"]
        mock_inspector.get_columns.return_value = [{"name": "id"}]

        mock_engine = MagicMock()

        # Patch inspect in the schema_validator module where it's imported
        with patch("app.db.schema_validator.inspect", return_value=mock_inspector):
            with patch("app.db.schema_validator._get_model_columns") as mock_get_model:
                # Model expects "email" but DB doesn't have it
                mock_get_model.return_value = {
                    "users": {"id", "email"},
                }

                from app.db.exceptions import KNOWN_EXCEPTIONS
                result = validate_schema_drift_sync(mock_engine, KNOWN_EXCEPTIONS)
                assert len(result) == 1, f"Expected 1 drift error, got: {result}"
                assert "users" in result[0] and "email" in result[0]

    def test_validate_schema_drift_sync_ignores_known_exceptions(self):
        """validate_schema_drift_sync ignores columns in KNOWN_EXCEPTIONS."""
        from app.db.schema_validator import validate_schema_drift_sync

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users"]
        mock_inspector.get_columns.return_value = [{"name": "id"}]

        mock_engine = MagicMock()

        KNOWN_EXCEPTIONS = {"users": {"virtual_column"}}

        # Patch inspect in the schema_validator module where it's imported
        with patch("app.db.schema_validator.inspect", return_value=mock_inspector):
            with patch("app.db.schema_validator._get_model_columns") as mock_get_model:
                mock_get_model.return_value = {
                    "users": {"id", "virtual_column", "email"},
                }

                result = validate_schema_drift_sync(mock_engine, KNOWN_EXCEPTIONS)
                assert len(result) == 1, f"Expected 1 drift error for email, got: {result}"
                assert "users" in result[0] and "email" in result[0]
                assert "virtual_column" not in result[0]

    def test_validate_schema_drift_sync_detects_missing_table(self):
        """validate_schema_drift_sync detects when model has table missing from DB."""
        from app.db.schema_validator import validate_schema_drift_sync

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users"]
        mock_inspector.get_columns.return_value = [{"name": "id"}]

        mock_engine = MagicMock()

        # Patch inspect in the schema_validator module where it's imported
        with patch("app.db.schema_validator.inspect", return_value=mock_inspector):
            with patch("app.db.schema_validator._get_model_columns") as mock_get_model:
                mock_get_model.return_value = {
                    "users": {"id"},
                    "orders": {"id", "total"},
                }

                from app.db.exceptions import KNOWN_EXCEPTIONS
                result = validate_schema_drift_sync(mock_engine, KNOWN_EXCEPTIONS)
                assert len(result) == 1, f"Expected 1 drift error, got: {result}"
                assert "orders" in result[0]

    def test_validate_schema_drift_sync_multiple_drift_errors(self):
        """validate_schema_drift_sync returns all drift errors, not just first."""
        from app.db.schema_validator import validate_schema_drift_sync

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["users"]
        mock_inspector.get_columns.return_value = [{"name": "id"}]

        mock_engine = MagicMock()

        # Patch inspect in the schema_validator module where it's imported
        with patch("app.db.schema_validator.inspect", return_value=mock_inspector):
            with patch("app.db.schema_validator._get_model_columns") as mock_get_model:
                mock_get_model.return_value = {
                    "users": {"id", "email", "created_at"},
                }

                from app.db.exceptions import KNOWN_EXCEPTIONS
                result = validate_schema_drift_sync(mock_engine, KNOWN_EXCEPTIONS)
                assert len(result) == 2, f"Expected 2 drift errors, got: {len(result)}: {result}"
