"""Admin account roles: POST/PUT /admin-users.

- role must be one of the five RBAC roles (422 otherwise, nothing written);
- a superadmin can create and assign every role, superadmin included;
- the last active superadmin cannot be demoted or deactivated (no lockout).
"""

import uuid

import pytest
from sqlalchemy import select, update

from app.models.models import AdminUser

ROLES = ["superadmin", "admin", "helpdesk", "auditor", "readonly"]
PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.limiter import limiter

    limiter.reset()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _name(prefix: str = "adm") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


async def _create(client, token, **fields):
    body = {"username": _name(), "password": PASSWORD, **fields}
    return await client.post("/admin-users", json=body, headers=_auth(token))


async def _get(db, username: str) -> AdminUser | None:
    db.expire_all()
    return (
        await db.execute(select(AdminUser).where(AdminUser.username == username))
    ).scalars().first()


@pytest.fixture
async def only_superadmin(test_db):
    """Make test_superadmin the only active superadmin for the test, then restore."""
    others = (
        await test_db.execute(
            select(AdminUser.id).where(
                AdminUser.role == "superadmin",
                AdminUser.is_active == 1,
                AdminUser.username != "test_superadmin",
            )
        )
    ).scalars().all()
    if others:
        await test_db.execute(
            update(AdminUser).where(AdminUser.id.in_(others)).values(is_active=0)
        )
        await test_db.commit()
    me = await _get(test_db, "test_superadmin")
    yield me
    if others:
        await test_db.execute(
            update(AdminUser).where(AdminUser.id.in_(others)).values(is_active=1)
        )
        await test_db.commit()


# ── Role validation ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", ROLES)
async def test_superadmin_can_create_every_role(async_client, superadmin_token, test_db, role):
    resp = await _create(async_client, superadmin_token, role=role)
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == role
    assert (await _get(test_db, resp.json()["username"])).role == role


async def test_create_without_role_still_defaults_to_admin(async_client, superadmin_token):
    resp = await _create(async_client, superadmin_token)
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "admin"


async def test_create_with_unknown_role_is_422_and_writes_nothing(
    async_client, superadmin_token, test_db
):
    username = _name()
    resp = await async_client.post(
        "/admin-users",
        json={"username": username, "password": PASSWORD, "role": "superadmn"},
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 422, resp.text
    assert await _get(test_db, username) is None


async def test_update_with_unknown_role_is_422_and_keeps_role(
    async_client, superadmin_token, test_db
):
    created = (await _create(async_client, superadmin_token, role="helpdesk")).json()
    resp = await async_client.put(
        f"/admin-users/{created['id']}", json={"role": "root"}, headers=_auth(superadmin_token)
    )
    assert resp.status_code == 422, resp.text
    assert (await _get(test_db, created["username"])).role == "helpdesk"


async def test_update_role_between_valid_roles(async_client, superadmin_token, test_db):
    created = (await _create(async_client, superadmin_token, role="readonly")).json()
    resp = await async_client.put(
        f"/admin-users/{created['id']}",
        json={"role": "superadmin"},
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 200, resp.text
    assert (await _get(test_db, created["username"])).role == "superadmin"


async def test_admin_role_still_cannot_create_admin_accounts(async_client, admin_token):
    resp = await _create(async_client, admin_token, role="superadmin")
    assert resp.status_code == 403


# ── Last active superadmin ──────────────────────────────────────────────────


async def test_last_superadmin_cannot_demote_self(
    async_client, superadmin_token, test_db, only_superadmin
):
    resp = await async_client.put(
        f"/admin-users/{only_superadmin.id}", json={"role": "admin"}, headers=_auth(superadmin_token)
    )
    assert resp.status_code == 400, resp.text
    assert "last active superadmin" in resp.json()["detail"]
    assert (await _get(test_db, "test_superadmin")).role == "superadmin"


async def test_last_superadmin_cannot_deactivate_self(
    async_client, superadmin_token, test_db, only_superadmin
):
    resp = await async_client.put(
        f"/admin-users/{only_superadmin.id}", json={"is_active": 0}, headers=_auth(superadmin_token)
    )
    assert resp.status_code == 400, resp.text
    assert (await _get(test_db, "test_superadmin")).is_active == 1


async def test_last_superadmin_can_still_change_own_email(
    async_client, superadmin_token, test_db, only_superadmin
):
    email = f"{_name('sa')}@example.com"
    resp = await async_client.put(
        f"/admin-users/{only_superadmin.id}",
        json={"email": email, "role": "superadmin", "is_active": 1},
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 200, resp.text
    assert (await _get(test_db, "test_superadmin")).email == email


async def test_superadmin_can_be_demoted_when_another_is_active(
    async_client, superadmin_token, test_db
):
    created = (await _create(async_client, superadmin_token, role="superadmin")).json()
    resp = await async_client.put(
        f"/admin-users/{created['id']}",
        json={"role": "auditor", "is_active": 0},
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 200, resp.text
    row = await _get(test_db, created["username"])
    assert (row.role, row.is_active) == ("auditor", 0)


async def test_other_superadmin_with_nonzero_is_active_counts_as_active(
    async_client, superadmin_token, test_db, only_superadmin
):
    """Login treats any non-zero is_active as active, so the guard must too."""
    created = (await _create(async_client, superadmin_token, role="superadmin")).json()
    await test_db.execute(
        update(AdminUser).where(AdminUser.id == only_superadmin.id).values(is_active=2)
    )
    await test_db.commit()
    try:
        resp = await async_client.put(
            f"/admin-users/{created['id']}", json={"role": "admin"}, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 200, resp.text
    finally:
        await test_db.execute(
            update(AdminUser).where(AdminUser.id == only_superadmin.id).values(is_active=1)
        )
        await test_db.commit()
