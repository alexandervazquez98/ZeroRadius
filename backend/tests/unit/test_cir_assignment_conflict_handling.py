from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from starlette.requests import Request

from app.models.models import UserNasPrivilegeMap
from app.routers import cir
from app.schemas.schemas import CIRAssignmentPayload


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


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/cir/assignments",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_existing_cir_assignment_unique_integrity_conflict_returns_http_409(monkeypatch):
    existing = UserNasPrivilegeMap(
        username="alice",
        target_key="tk",
        radius_group="cir_basic",
    )
    existing.id = 123

    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.commit.side_effect = IntegrityError(
        "update", {}, Exception("UNIQUE constraint failed: user_nas_privilege_map.username, user_nas_privilege_map.nas_ip")
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return existing

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_cir_assignment_non_unique_integrity_error_returns_http_422(monkeypatch):
    existing = UserNasPrivilegeMap(
        username="alice",
        target_key="tk",
        radius_group="cir_basic",
    )
    existing.id = 123

    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.commit.side_effect = IntegrityError(
        "update", {}, Exception("FOREIGN KEY constraint failed")
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return existing

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_unique_integrity_conflict_returns_http_409_and_rolls_back(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("integrity violation", errno=1062),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    assert "alice" in str(exc_info.value.detail)
    assert "10.0.0.10" in str(exc_info.value.detail)
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_postgres_sqlstate_23505_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("duplicate key value violates unique constraint", sqlstate="23505"),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_postgres_pgcode_23505_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("duplicate key value violates unique constraint", pgcode="23505"),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_postgres_non_unique_sqlstate_returns_http_422(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("insert violates foreign key constraint", sqlstate="23503"),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_sqlite_unique_errorcode_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("UNIQUE constraint failed", sqlite_errorcode=2067),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_mysql_errno_from_args_duplicate_key_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErrArgsFallback(1062, "Duplicate entry 'alice-10.0.0.10' for key 'uq_user_nas_ip'"),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_sqlite_primarykey_errorcode_1555_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr("PRIMARY KEY constraint failed", sqlite_errorcode=1555),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_sqlite_primarykey_errorname_returns_http_409(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr(
            "PRIMARY KEY constraint failed",
            sqlite_errorname="SQLITE_CONSTRAINT_PRIMARYKEY",
        ),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_row_race_sqlite_non_unique_errorname_returns_http_422(monkeypatch):
    payload = CIRAssignmentPayload(
        username="alice",
        nas_ip="10.0.0.10",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.add = Mock()
    db.commit.side_effect = IntegrityError(
        "insert",
        {},
        _DbErr(
            "FOREIGN KEY constraint failed",
            sqlite_errorname="SQLITE_CONSTRAINT_FOREIGNKEY",
        ),
    )

    async def _fake_find_existing_assignment(_db, _payload):
        return None

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "_find_existing_assignment", _fake_find_existing_assignment)
    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.create_or_replace_cir_assignment(
            request=_request(),
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_cir_assignment_unique_integrity_conflict_returns_http_409(monkeypatch):
    assignment = UserNasPrivilegeMap(
        username="bob",
        target_key="tk2",
        radius_group="cir_basic",
    )
    assignment.id = 456

    payload = CIRAssignmentPayload(
        username="bob",
        nas_ip="10.0.0.20",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(assignment)
    db.commit.side_effect = IntegrityError(
        "update", {}, Exception("Duplicate entry 'bob-10.0.0.20' for key 'uq_user_nas_ip'")
    )

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.update_cir_assignment(
            request=_request(),
            assignment_id=assignment.id,
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 409
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_cir_assignment_non_unique_integrity_error_returns_http_422(monkeypatch):
    assignment = UserNasPrivilegeMap(
        username="bob",
        target_key="tk2",
        radius_group="cir_basic",
    )
    assignment.id = 457

    payload = CIRAssignmentPayload(
        username="bob",
        nas_ip="10.0.0.20",
        radius_group="cir_premium",
    )

    db = AsyncMock()
    db.execute.return_value = _ScalarResult(assignment)
    db.commit.side_effect = IntegrityError(
        "update", {}, Exception("FOREIGN KEY constraint failed")
    )

    async def _fake_validate_segment_exception(_db, _payload, exclude_id=None):
        return None

    monkeypatch.setattr(cir, "validate_segment_exception", _fake_validate_segment_exception)

    with pytest.raises(HTTPException) as exc_info:
        await cir.update_cir_assignment(
            request=_request(),
            assignment_id=assignment.id,
            payload=payload,
            db=db,
            current_user=None,
        )

    assert exc_info.value.status_code == 422
    db.rollback.assert_awaited_once()
