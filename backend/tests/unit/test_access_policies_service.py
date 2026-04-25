from unittest.mock import AsyncMock, Mock, patch
import importlib

import pytest
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

from app.models.models import AccessPolicyAssignment
from app.services import access_policies_service
from app.schemas.access_policies import AccessPolicyAssignmentCreate


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value


class _DbErr:
    def __init__(self, message: str = "", **kwargs):
        self.args = (message,)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return self.args[0]


class _DbErrArgsFallback:
    def __init__(self, code: int, message: str):
        self.args = (code, message)

    def __str__(self):
        return str(self.args[1])


@pytest.mark.asyncio
async def test_unique_integrity_conflict_returns_http_409():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "update", {}, Exception("UNIQUE constraint failed: access_policy_assignments.username, access_policy_assignments.nas_ip")
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_non_unique_integrity_error_returns_http_422():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "update", {}, Exception("FOREIGN KEY constraint failed")
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_postgres_sqlstate_23505_returns_http_409():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "insert",
        {},
        _DbErr("duplicate key value violates unique constraint", sqlstate="23505"),
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_postgres_pgcode_23505_returns_http_409():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "insert",
        {},
        _DbErr("duplicate key value violates unique constraint", pgcode="23505"),
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_sqlite_unique_errorcode_returns_http_409():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "insert",
        {},
        _DbErr("UNIQUE constraint failed", sqlite_errorcode=2067),
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_mysql_errno_from_args_duplicate_key_returns_http_409():
    payload = AccessPolicyAssignmentCreate(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    err = IntegrityError(
        "insert",
        {},
        _DbErrArgsFallback(1062, "Duplicate entry 'alice-10.0.0.10' for key 'uq_user_nas_ip'"),
    )

    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_assignment_integrity_error(payload, err)

    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# Category Membership Guard — Unit Tests
# ---------------------------------------------------------------------------

def test_raise_category_membership_error_returns_409_with_username_and_category():
    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_category_membership_error("alice", "APDevices")

    assert exc_info.value.status_code == 409
    assert "alice" in exc_info.value.detail
    assert "APDevices" in exc_info.value.detail
    assert "not a member" in exc_info.value.detail


def test_raise_category_membership_error_with_unknown_category():
    with pytest.raises(HTTPException) as exc_info:
        access_policies_service.raise_category_membership_error("bob", "ID 999")

    assert exc_info.value.status_code == 409
    assert "bob" in exc_info.value.detail


class _FakeSession:
    """Minimal fake AsyncSession that returns pre-configured results."""

    def __init__(self, results: list):
        self._results = results
        self._index = 0

    async def execute(self, stmt):
        result = self._results[self._index] if self._index < len(self._results) else _ScalarResult(None)
        self._index += 1
        return result


@pytest.mark.asyncio
async def test_validate_category_membership_allows_when_guard_disabled(monkeypatch):
    """When CATEGORY_MEMBERSHIP_GUARD_ENABLED=false, no DB queries are made."""
    # Force the flag to false at module level
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", False)

    # If we got here without raising, the guard allowed passage
    # (The function would raise if flag is true but no membership found)
    fake_session = _FakeSession([])
    await access_policies_service.validate_category_membership(
        fake_session, "alice", nas_category_id=1, calling_station_id="00:11:22:33:44:55"
    )
    # No exception means guard passed (or was bypassed)


@pytest.mark.asyncio
async def test_validate_category_membership_raises_409_when_no_membership_and_guard_enabled(
    monkeypatch,
):
    """When flag=true and no DeviceRegistry or existing assignment, raise 409."""
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # Both queries return None (no membership)
    fake_session = _FakeSession([
        _ScalarResult(None),  # DeviceRegistry query
        _ScalarResult(None),  # AccessPolicyAssignment query
        _ScalarResult("APDevices"),  # NasCategory name lookup
    ])

    with pytest.raises(HTTPException) as exc_info:
        await access_policies_service.validate_category_membership(
            fake_session, "alice", nas_category_id=1, calling_station_id="00:11:22:33:44:55"
        )

    assert exc_info.value.status_code == 409
    assert "alice" in exc_info.value.detail
    assert "APDevices" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_category_membership_allows_via_device_registry(
    monkeypatch,
):
    """When flag=true and DeviceRegistry has the MAC+category, allow."""
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # DeviceRegistry returns a device → membership confirmed
    class _DeviceResult:
        def __init__(self):
            self._value = Mock()  # non-None means found

        def scalars(self):
            return self

        def first(self):
            return self._value

    fake_session = _FakeSession([_DeviceResult()])

    # Should not raise
    await access_policies_service.validate_category_membership(
        fake_session, "alice", nas_category_id=1, calling_station_id="001122334455"
    )


@pytest.mark.asyncio
async def test_validate_category_membership_allows_via_existing_assignment(
    monkeypatch,
):
    """When flag=true and user has existing assignment in category, allow."""
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # First query (DeviceRegistry with MAC) returns None
    # Second query (existing assignment) returns a record
    class _AssignResult:
        def __init__(self):
            self._value = Mock()

        def scalars(self):
            return self

        def first(self):
            return self._value

    fake_session = _FakeSession([_ScalarResult(None), _AssignResult()])

    # Should not raise
    await access_policies_service.validate_category_membership(
        fake_session, "alice", nas_category_id=1, calling_station_id="00:11:22:33:44:55"
    )


@pytest.mark.asyncio
async def test_validate_category_membership_skips_device_registry_when_no_mac(
    monkeypatch,
):
    """When calling_station_id is None, skip DeviceRegistry path and check assignments."""
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    class _AssignResult:
        def __init__(self):
            self._value = Mock()

        def scalars(self):
            return self

        def first(self):
            return self._value

    # Only one result needed — the AccessPolicyAssignment query
    fake_session = _FakeSession([_AssignResult()])

    # Should not raise (assignment found)
    await access_policies_service.validate_category_membership(
        fake_session, "alice", nas_category_id=1, calling_station_id=None
    )


@pytest.mark.asyncio
async def test_validate_category_membership_falls_back_when_device_registry_fails(
    monkeypatch,
):
    """When DeviceRegistry lookup returns no match but assignment exists, allow."""
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    class _AssignResult:
        def __init__(self):
            self._value = Mock()

        def scalars(self):
            return self

        def first(self):
            return self._value

    fake_session = _FakeSession([_ScalarResult(None), _AssignResult()])

    # Should not raise — membership confirmed via existing assignment
    await access_policies_service.validate_category_membership(
        fake_session, "alice", nas_category_id=1, calling_station_id="00:11:22:33:44:55"
    )
