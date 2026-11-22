"""Self-service password setup links (#101 part C).

Spec: odd/tasks/radius-password-setup-link.md (S1-S7).
- S1 only the URL token is generated (shown once); the DB stores its SHA-256.
- S2 the link records who generated it; S5 GET /users shows its status.
- S3 valid for 72 hours; S4 single use, a new link replaces the previous one.
- S6 the current password is blocked as soon as the link is generated.
"""

import datetime
import hashlib
import json

import pytest
from sqlalchemy import select, update

from app.core.radius_passwords import nt_hash
from app.models.models import PasswordSetupLink, RadCheck


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.limiter import limiter

    limiter.reset()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _create_user(client, token, username, attribute="Cleartext-Password", value="old-pw"):
    resp = await client.post(
        "/users/check",
        json={"username": username, "attribute": attribute, "op": ":=", "value": value},
        headers=_auth(token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _generate(client, token, row_id, **body):
    return await client.post(f"/users/check/{row_id}/setup-link", json=body, headers=_auth(token))


async def _row(test_db, row_id):
    test_db.expire_all()
    return (await test_db.execute(select(RadCheck).where(RadCheck.id == row_id))).scalars().one()


async def _listing_row(client, token, row_id):
    resp = await client.get("/users", headers=_auth(token))
    assert resp.status_code == 200
    return next(r for r in resp.json() if r["id"] == row_id)


class TestGenerateLink:
    async def test_generate_returns_token_once_and_stores_only_its_hash(
        self, async_client, superadmin_token, test_db
    ):
        user = await _create_user(async_client, superadmin_token, "sl_gen")
        resp = await _generate(async_client, superadmin_token, user["id"], password_type="NT-Password")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        token = body["token"]
        assert len(token) >= 32
        assert body["username"] == "sl_gen"
        assert body["attribute"] == "NT-Password"

        test_db.expire_all()
        links = (
            await test_db.execute(select(PasswordSetupLink).where(PasswordSetupLink.radcheck_id == user["id"]))
        ).scalars().all()
        assert len(links) == 1
        assert links[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert links[0].created_by == "test_superadmin"
        lifetime = links[0].expires_at - links[0].created_at
        assert datetime.timedelta(hours=71, minutes=59) <= lifetime <= datetime.timedelta(hours=72, minutes=1)

        listing = await async_client.get("/users", headers=_auth(superadmin_token))
        assert token not in listing.text

    async def test_regression_generating_blocks_current_password(
        self, async_client, superadmin_token, test_db
    ):
        user = await _create_user(async_client, superadmin_token, "sl_block", value="old-pw")
        resp = await _generate(async_client, superadmin_token, user["id"])
        assert resp.status_code == 200, resp.text
        row = await _row(test_db, user["id"])
        assert row.attribute == "Cleartext-Password"
        assert row.value != "old-pw"
        assert row.value

    async def test_status_is_visible_in_users_panel(self, async_client, superadmin_token):
        user = await _create_user(async_client, superadmin_token, "sl_status")
        before = await _listing_row(async_client, superadmin_token, user["id"])
        assert before["setup_link"] is None

        await _generate(async_client, superadmin_token, user["id"])
        row = await _listing_row(async_client, superadmin_token, user["id"])
        link = row["setup_link"]
        assert link["status"] == "pending"
        assert link["created_by"] == "test_superadmin"
        assert link["expires_at"]
        assert link["used_at"] is None

    async def test_new_link_replaces_previous_one(self, async_client, superadmin_token):
        user = await _create_user(async_client, superadmin_token, "sl_replace")
        first = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        second = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]

        resp = await async_client.get(f"/password-setup/{first}")
        assert resp.status_code == 410
        resp = await async_client.get(f"/password-setup/{second}")
        assert resp.status_code == 200

    async def test_generation_is_audited_without_token(self, async_client, superadmin_token, auditor_token):
        user = await _create_user(async_client, superadmin_token, "sl_audit")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        audit = await async_client.get(
            "/audit/admin", params={"search": "sl_audit"}, headers=_auth(auditor_token)
        )
        rows = [r for r in audit.json() if r["action"] == "PASSWORD_SETUP_LINK_CREATED"]
        assert len(rows) == 1 and rows[0]["admin_user"] == "test_superadmin"
        assert token not in audit.text

    @pytest.mark.parametrize("token_fixture", ["helpdesk_token", "auditor_token"])
    async def test_only_admins_can_generate(self, async_client, superadmin_token, token_fixture, request, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_rbac", value="keep-me")
        resp = await _generate(async_client, request.getfixturevalue(token_fixture), user["id"])
        assert resp.status_code == 403
        assert (await _row(test_db, user["id"])).value == "keep-me"

    async def test_non_password_row_and_non_settable_type_rejected(self, async_client, superadmin_token):
        exp = await _create_user(async_client, superadmin_token, "sl_exp", "Expiration", "01 Jan 2030 00:00")
        assert (await _generate(async_client, superadmin_token, exp["id"])).status_code == 422
        crypt = await _create_user(async_client, superadmin_token, "sl_crypt", "Crypt-Password", "$1$x$y")
        assert (await _generate(async_client, superadmin_token, crypt["id"])).status_code == 422
        assert (await _generate(async_client, superadmin_token, 999999)).status_code == 404


class TestUseLink:
    async def test_link_sets_password_once(self, async_client, superadmin_token, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_use")
        token = (await _generate(async_client, superadmin_token, user["id"], password_type="NT-Password")).json()["token"]

        info = await async_client.get(f"/password-setup/{token}")
        assert info.status_code == 200
        assert info.json()["username"] == "sl_use"
        assert info.json()["expires_at"]

        resp = await async_client.post(f"/password-setup/{token}", json={"password": "password"})
        assert resp.status_code == 200, resp.text
        row = await _row(test_db, user["id"])
        assert (row.attribute, row.value) == ("NT-Password", nt_hash("password"))

        again = await async_client.post(f"/password-setup/{token}", json={"password": "other"})
        assert again.status_code == 410
        assert (await _row(test_db, user["id"])).value == nt_hash("password")

        status = (await _listing_row(async_client, superadmin_token, user["id"]))["setup_link"]
        assert status["status"] == "used"
        assert status["used_at"]

    async def test_regression_expired_link_is_rejected(self, async_client, superadmin_token, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_expired")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        blocked_value = (await _row(test_db, user["id"])).value
        await test_db.execute(
            update(PasswordSetupLink)
            .where(PasswordSetupLink.radcheck_id == user["id"])
            .values(expires_at=datetime.datetime(2000, 1, 1))
        )
        await test_db.commit()

        assert (await async_client.get(f"/password-setup/{token}")).status_code == 410
        resp = await async_client.post(f"/password-setup/{token}", json={"password": "new-pw"})
        assert resp.status_code == 410
        assert (await _row(test_db, user["id"])).value == blocked_value
        status = (await _listing_row(async_client, superadmin_token, user["id"]))["setup_link"]
        assert status["status"] == "expired"

    async def test_unknown_token_is_404_and_empty_password_422(self, async_client, superadmin_token):
        assert (await async_client.get("/password-setup/not-a-real-token")).status_code == 404
        user = await _create_user(async_client, superadmin_token, "sl_empty")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.post(f"/password-setup/{token}", json={"password": ""})
        assert resp.status_code == 422
        assert (await async_client.get(f"/password-setup/{token}")).status_code == 200

    async def test_use_is_audited_without_password(self, async_client, superadmin_token, auditor_token):
        user = await _create_user(async_client, superadmin_token, "sl_use_audit")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        await async_client.post(f"/password-setup/{token}", json={"password": "my-secret-pw"})
        audit = await async_client.get(
            "/audit/admin", params={"search": "sl_use_audit"}, headers=_auth(auditor_token)
        )
        assert any(r["action"] == "PASSWORD_SETUP_LINK_USED" for r in audit.json())
        assert "my-secret-pw" not in audit.text

    async def test_admin_reset_revokes_pending_link(self, async_client, superadmin_token):
        user = await _create_user(async_client, superadmin_token, "sl_reset")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.post(
            f"/users/check/{user['id']}/reset-password", json={"password": "admin-set"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200
        assert (await async_client.get(f"/password-setup/{token}")).status_code == 410
        status = (await _listing_row(async_client, superadmin_token, user["id"]))["setup_link"]
        assert status["status"] == "revoked"

    async def test_deleting_the_user_removes_its_links(self, async_client, superadmin_token, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_delete")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.delete(f"/users/check/{user['id']}", headers=_auth(superadmin_token))
        assert resp.status_code == 200
        assert (await async_client.get(f"/password-setup/{token}")).status_code == 404


class TestLinkInvalidatedByEdit:
    """Verifier finding: an admin edit of the row must invalidate a pending link."""

    async def test_regression_attribute_change_revokes_link(self, async_client, superadmin_token, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_edit_attr")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.put(
            f"/users/check/{user['id']}",
            json={"attribute": "Simultaneous-Use", "value": "1"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text

        assert (await async_client.post(f"/password-setup/{token}", json={"password": "pw"})).status_code == 410
        row = await _row(test_db, user["id"])
        assert (row.attribute, row.value) == ("Simultaneous-Use", "1")
        status = (await _listing_row(async_client, superadmin_token, user["id"]))["setup_link"]
        assert status["status"] == "revoked"

    async def test_regression_admin_password_via_put_revokes_link(self, async_client, superadmin_token, test_db):
        user = await _create_user(async_client, superadmin_token, "sl_edit_pw")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.put(
            f"/users/check/{user['id']}", json={"value": "admin-pw"}, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 200, resp.text
        assert (await async_client.post(f"/password-setup/{token}", json={"password": "user-pw"})).status_code == 410
        assert (await _row(test_db, user["id"])).value == "admin-pw"

    async def test_regression_rename_revokes_link(self, async_client, superadmin_token):
        user = await _create_user(async_client, superadmin_token, "sl_edit_name")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.put(
            f"/users/check/{user['id']}", json={"username": "sl_edit_name2"}, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 200, resp.text
        assert (await async_client.get(f"/password-setup/{token}")).status_code == 410

    async def test_op_only_edit_keeps_link(self, async_client, superadmin_token):
        user = await _create_user(async_client, superadmin_token, "sl_edit_op")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        resp = await async_client.put(
            f"/users/check/{user['id']}", json={"op": ":="}, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 200, resp.text
        assert (await async_client.get(f"/password-setup/{token}")).status_code == 200

    async def test_regression_link_refuses_non_password_row(self, async_client, superadmin_token, test_db):
        """Defense in depth: even if a link stayed pending, never overwrite a non-password row."""
        user = await _create_user(async_client, superadmin_token, "sl_direct")
        token = (await _generate(async_client, superadmin_token, user["id"])).json()["token"]
        await test_db.execute(
            update(RadCheck).where(RadCheck.id == user["id"]).values(attribute="Simultaneous-Use", value="1")
        )
        await test_db.commit()
        assert (await async_client.post(f"/password-setup/{token}", json={"password": "pw"})).status_code == 410
        row = await _row(test_db, user["id"])
        assert (row.attribute, row.value) == ("Simultaneous-Use", "1")
