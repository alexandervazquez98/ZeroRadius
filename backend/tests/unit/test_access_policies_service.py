from unittest.mock import AsyncMock, Mock

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
