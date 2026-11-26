"""
Integration tests: sliding session refresh (#135).

Tokens expire after the idle period (ACCESS_TOKEN_EXPIRE_MINUTES, default
30). While the admin is active the frontend calls POST /auth/refresh, which
issues a new token with the same session start (`auth_time`) until the
absolute lifetime (SESSION_MAX_HOURS, default 12) runs out. Refresh re-reads
the admin from the DB, so a disabled or deleted admin cannot refresh.
"""

import time
import uuid

import jwt
import pytest
from sqlalchemy import delete

from app.core import security
from app.core.security import ALGORITHM, SECRET_KEY
from app.models.models import AdminUser

_PW_HASH = "$2b$12$o1OT5/N.USFa0TLuT482HOhFm1UtQ/BQhnZ.si36AZgZbFp0Sjzgu"  # TestPassword1!
EXPIRED = "Session expired. Please sign in again."


def _token(sub, auth_time=None, exp_in=600, **extra):
    now = int(time.time())
    claims = {"sub": sub, "role": "readonly", "exp": now + exp_in, **extra}
    if auth_time is not None:
        claims["auth_time"] = auth_time
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def _claims(token):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


async def _refresh(client, token):
    return await client.post("/auth/refresh", headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
async def make_admin(test_db):
    created = []

    async def _make(role="admin", is_active=1):
        name = f"sess_{uuid.uuid4().hex[:8]}"
        test_db.add(AdminUser(username=name, hashed_password=_PW_HASH, is_active=is_active,
                              force_password_change=0, role=role))
        await test_db.commit()
        created.append(name)
        return name

    yield _make
    await test_db.execute(delete(AdminUser).where(AdminUser.username.in_(created)))
    await test_db.commit()


class TestLoginToken:
    async def test_login_token_carries_session_start_and_idle_expiry(self, async_client, make_admin):
        # Own admin: other tests change test_superadmin's password.
        name = await make_admin()
        before = int(time.time())
        resp = await async_client.post(
            "/auth/token",
            data={"username": name, "password": "TestPassword1!"},
            headers={"X-Forwarded-For": "198.18.135.1"},
        )
        assert resp.status_code == 200
        claims = _claims(resp.json()["access_token"])
        assert before <= claims["auth_time"] <= int(time.time())
        idle = security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(claims["exp"] - (claims["auth_time"] + idle)) <= 2

    async def test_invalid_credentials_still_return_the_login_error(self, async_client):
        resp = await async_client.post(
            "/auth/token",
            data={"username": "test_readonly", "password": "WrongPassword!"},
            headers={"X-Forwarded-For": "198.18.135.2"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect username or password"


class TestRefresh:
    async def test_refresh_extends_the_idle_window_and_keeps_the_session_start(
        self, async_client, make_admin
    ):
        name = await make_admin()
        start = int(time.time()) - 3600
        resp = await _refresh(async_client, _token(name, auth_time=start, exp_in=60))
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        claims = _claims(body["access_token"])
        assert claims["sub"] == name
        assert claims["auth_time"] == start
        idle = security.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert abs(claims["exp"] - (int(time.time()) + idle)) <= 2

    async def test_refresh_never_goes_past_the_absolute_lifetime(self, async_client, make_admin):
        name = await make_admin()
        max_s = security.SESSION_MAX_HOURS * 3600
        start = int(time.time()) - max_s + 300  # 5 min of session left
        resp = await _refresh(async_client, _token(name, auth_time=start))
        assert resp.status_code == 200
        assert _claims(resp.json()["access_token"])["exp"] == start + max_s

    async def test_refresh_after_the_absolute_lifetime_is_rejected(self, async_client, make_admin):
        name = await make_admin()
        start = int(time.time()) - security.SESSION_MAX_HOURS * 3600 - 60
        resp = await _refresh(async_client, _token(name, auth_time=start))
        assert resp.status_code == 401
        assert resp.json()["detail"] == EXPIRED

    async def test_token_without_session_start_cannot_refresh(self, async_client, make_admin):
        # Tokens issued before #135 have no auth_time: sign in once more.
        name = await make_admin()
        resp = await _refresh(async_client, _token(name))
        assert resp.status_code == 401
        assert resp.json()["detail"] == EXPIRED

    async def test_expired_token_cannot_refresh(self, async_client, make_admin):
        name = await make_admin()
        resp = await _refresh(async_client, _token(name, auth_time=int(time.time()) - 120, exp_in=-60))
        assert resp.status_code == 401

    async def test_disabled_admin_cannot_refresh(self, async_client, make_admin):
        name = await make_admin(is_active=0)
        resp = await _refresh(async_client, _token(name, auth_time=int(time.time())))
        assert resp.status_code == 401

    async def test_deleted_admin_cannot_refresh(self, async_client):
        resp = await _refresh(async_client, _token("ghost_admin_135", auth_time=int(time.time())))
        assert resp.status_code == 401

    async def test_refresh_reads_role_from_the_database(self, async_client, make_admin):
        name = await make_admin(role="auditor")
        resp = await _refresh(async_client, _token(name, auth_time=int(time.time())))  # token says readonly
        claims = _claims(resp.json()["access_token"])
        assert claims["role"] == "auditor"
        assert claims["force_change"] is False

    async def test_refresh_requires_a_token(self, async_client):
        assert (await async_client.post("/auth/refresh")).status_code == 401


@pytest.mark.parametrize(
    "raw, expected",
    [("", 12), ("8", 8), ("24", 24), ("abc", 12)],
)
def test_session_max_hours_parsing(raw, expected):
    assert security.parse_session_max_hours(raw) == expected


@pytest.mark.parametrize("raw", ["25", "0", "-1"])
def test_session_max_hours_out_of_range_is_rejected(raw):
    with pytest.raises(RuntimeError, match="SESSION_MAX_HOURS"):
        security.parse_session_max_hours(raw)
