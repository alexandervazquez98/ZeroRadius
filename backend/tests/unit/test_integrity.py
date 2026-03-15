"""
T37 — Unit tests for IntegrityHashService (compute_hash).

Tests cover:
- Determinism
- Hash prefix format
- Hash length
- Tamper detection (reply field, username field)
- Missing fields handled as empty string
- Field insertion order irrelevant
"""

import pytest
from app.services.integrity import compute_hash, CRITICAL_FIELDS_AUTH


class TestComputeHash:
    def test_deterministic_same_input_same_hash(self):
        """The same input always produces the same hash."""
        record = {
            "username": "jperez",
            "authdate": "2026-01-01T10:00:00",
            "nas_ip_address": "192.168.1.1",
            "reply": "Access-Accept",
            "calling_station_id": "10.0.0.1",
        }
        h1 = compute_hash(record, CRITICAL_FIELDS_AUTH)
        h2 = compute_hash(record, CRITICAL_FIELDS_AUTH)
        assert h1 == h2

    def test_hash_prefix_sha256(self):
        """The hash begins with 'sha256:'."""
        record = {
            "username": "x",
            "authdate": "t",
            "nas_ip_address": "1",
            "reply": "y",
            "calling_station_id": "z",
        }
        assert compute_hash(record, CRITICAL_FIELDS_AUTH).startswith("sha256:")

    def test_hash_length(self):
        """sha256: + 64 hex chars = 71 characters."""
        record = {
            "username": "x",
            "authdate": "t",
            "nas_ip_address": "1",
            "reply": "y",
            "calling_station_id": "z",
        }
        assert len(compute_hash(record, CRITICAL_FIELDS_AUTH)) == 71

    def test_tamper_detection_reply_change(self):
        """Changing the reply field produces a different hash."""
        base = {
            "username": "jperez",
            "authdate": "2026-01-01T10:00:00",
            "nas_ip_address": "192.168.1.1",
            "reply": "Access-Accept",
            "calling_station_id": "10.0.0.1",
        }
        tampered = {**base, "reply": "Access-Reject"}
        assert compute_hash(base, CRITICAL_FIELDS_AUTH) != compute_hash(
            tampered, CRITICAL_FIELDS_AUTH
        )

    def test_tamper_detection_username_change(self):
        """Changing the username field produces a different hash."""
        base = {
            "username": "jperez",
            "authdate": "2026-01-01T10:00:00",
            "nas_ip_address": "192.168.1.1",
            "reply": "Access-Accept",
            "calling_station_id": "10.0.0.1",
        }
        tampered = {**base, "username": "attacker"}
        assert compute_hash(base, CRITICAL_FIELDS_AUTH) != compute_hash(
            tampered, CRITICAL_FIELDS_AUTH
        )

    def test_missing_field_uses_empty_string(self):
        """Fields absent from the record do not raise KeyError."""
        record = {"username": "jperez"}  # all other fields missing
        h = compute_hash(record, CRITICAL_FIELDS_AUTH)
        assert h.startswith("sha256:")

    def test_field_order_irrelevant(self):
        """Key insertion order in the record dict does not affect the hash (canonical form)."""
        r1 = {
            "username": "a",
            "authdate": "b",
            "nas_ip_address": "c",
            "reply": "d",
            "calling_station_id": "e",
        }
        r2 = {
            "calling_station_id": "e",
            "reply": "d",
            "nas_ip_address": "c",
            "authdate": "b",
            "username": "a",
        }
        assert compute_hash(r1, CRITICAL_FIELDS_AUTH) == compute_hash(
            r2, CRITICAL_FIELDS_AUTH
        )

    def test_none_value_treated_as_empty(self):
        """None values in record fields are treated the same as empty string."""
        record_none = {
            "username": "jperez",
            "authdate": None,
            "nas_ip_address": "192.168.1.1",
            "reply": "Access-Accept",
            "calling_station_id": None,
        }
        record_empty = {
            "username": "jperez",
            "authdate": "",
            "nas_ip_address": "192.168.1.1",
            "reply": "Access-Accept",
            "calling_station_id": "",
        }
        # Both should produce the same hash (None → "" normalization)
        assert compute_hash(record_none, CRITICAL_FIELDS_AUTH) == compute_hash(
            record_empty, CRITICAL_FIELDS_AUTH
        )
