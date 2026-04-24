"""
Shared constants for database schema validation.

Columns that only exist in models for ORM convenience (relationships, hybrid
properties, etc.) and intentionally have no database column counterpart.
Add entries here ONLY with a comment explaining why.

This module is the single source of truth for schema validation exceptions.
It is used by:
- backend/app/db/schema_validator.py (runtime validation)
- backend/tests/unit/test_schema_sync.py (init.sql sync validation)

If you add a column here, you MUST add a comment explaining why it has no DB column.
"""

from typing import Final

# Columns that only exist in models for ORM convenience (relationships, etc.)
# and intentionally have no init.sql counterpart.  Add entries here ONLY with
# a comment explaining why.
KNOWN_EXCEPTIONS: Final[dict[str, set[str]]] = {
    # Example (do not remove comment, but example entry can be removed):
    # "some_table": {"virtual_column"},
}
