"""
app.db package — Database connection and schema validation.

Exports:
- session: Base, engine, SessionLocal, get_db
- exceptions: KNOWN_EXCEPTIONS for schema drift detection
- schema_validator: validate_schema_drift() for runtime schema validation
"""

from app.db.exceptions import KNOWN_EXCEPTIONS
from app.db.schema_validator import validate_schema_drift

__all__ = [
    "KNOWN_EXCEPTIONS",
    "validate_schema_drift",
]