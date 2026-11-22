"""
Integration tests: /users endpoint (radcheck CRUD).

Verifies:
- Any authenticated role can list RADIUS users (GET /users)
- Any authenticated role can create (POST /users/check) — no specific RBAC on users router
- Unauthenticated requests are rejected (401)
"""

import pytest


class TestUsersRead:
    """GET /users — list RADIUS users (radcheck)."""

    async def test_superadmin_can_list_users(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/users", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_list_users(self, async_client, admin_token):
        resp = await async_client.get(
            "/users", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_list_users(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/users", headers={"Authorization": f"Bearer {helpdesk_token}"}
        )
        assert resp.status_code == 200

    async def test_unauthenticated_cannot_list_users(self, async_client):
        resp = await async_client.get("/users")
        assert resp.status_code in (401, 403)


class TestUsersCreate:
    """POST /users/check — create RADIUS user check attribute."""

    async def test_superadmin_can_create_user(self, async_client, superadmin_token):
        payload = {
            "username": "integration_test_user_001",
            "attribute": "Cleartext-Password",
            "op": ":=",
            "value": "testpass",
        }
        resp = await async_client.post(
            "/users/check",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["username"] == "integration_test_user_001"

    async def test_helpdesk_can_create_user(self, async_client, helpdesk_token):
        payload = {
            "username": "integration_test_user_002",
            "attribute": "Cleartext-Password",
            "op": ":=",
            "value": "testpass",
        }
        resp = await async_client.post(
            "/users/check",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code in (200, 201)

    async def test_unauthenticated_cannot_create_user(self, async_client):
        payload = {
            "username": "ghost_user",
            "attribute": "Cleartext-Password",
            "op": ":=",
            "value": "testpass",
        }
        resp = await async_client.post("/users/check", json=payload)
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Issues #101 (part A) and #95: RADIUS credentials never leave radcheck
# ---------------------------------------------------------------------------

import hashlib
import json

from sqlalchemy import select

from app.models.models import RadCheck


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """This module creates many radcheck rows; keep each test under the
    30/minute limit of the users endpoints instead of depending on order."""
    from app.core.limiter import limiter

    limiter.reset()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _create(client, token, username, attribute, value):
    resp = await client.post(
        "/users/check",
        json={"username": username, "attribute": attribute, "op": ":=", "value": value},
        headers=_auth(token),
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


async def _stored(test_db, row_id):
    test_db.expire_all()
    row = (await test_db.execute(select(RadCheck).where(RadCheck.id == row_id))).scalars().one()
    return row.attribute, row.value


class TestCredentialsNotExposed:
    """GET /users and write responses never return a password value (#101-A)."""

    @pytest.mark.parametrize(
        "token_fixture", ["superadmin_token", "admin_token", "helpdesk_token", "auditor_token"]
    )
    async def test_regression_list_never_returns_password_value(
        self, async_client, superadmin_token, token_fixture, request
    ):
        await _create(async_client, superadmin_token, "cred_list_clear", "Cleartext-Password", "s3cret-clear")
        await _create(async_client, superadmin_token, "cred_list_md5", "MD5-Password", "s3cret-md5")

        token = request.getfixturevalue(token_fixture)
        resp = await async_client.get("/users", headers=_auth(token))
        assert resp.status_code == 200
        rows = {r["username"]: r for r in resp.json() if r["username"].startswith("cred_list_")}

        assert rows["cred_list_clear"]["value"] is None
        assert rows["cred_list_clear"]["has_password"] is True
        assert rows["cred_list_clear"]["attribute"] == "Cleartext-Password"
        assert rows["cred_list_md5"]["value"] is None
        assert rows["cred_list_md5"]["has_password"] is True
        body = resp.text
        assert "s3cret-clear" not in body
        assert hashlib.md5(b"s3cret-md5").hexdigest() not in body

    async def test_non_password_attribute_value_is_still_returned(
        self, async_client, superadmin_token
    ):
        await _create(async_client, superadmin_token, "cred_expiration", "Expiration", "01 Jan 2030 00:00")
        resp = await async_client.get("/users", headers=_auth(superadmin_token))
        row = next(r for r in resp.json() if r["username"] == "cred_expiration")
        assert row["value"] == "01 Jan 2030 00:00"
        assert row["has_password"] is False

    async def test_regression_create_response_has_no_password_value(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_create_md5", "MD5-Password", "pw-create")
        assert created["value"] is None
        assert created["has_password"] is True
        assert await _stored(test_db, created["id"]) == (
            "MD5-Password",
            hashlib.md5(b"pw-create").hexdigest(),
        )


class TestPasswordEdit:
    """PUT /users/check/{id} keeps or replaces the password safely (#95)."""

    async def test_regression_changing_type_without_password_is_rejected(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_edit_switch", "MD5-Password", "orig-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "Cleartext-Password"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert "new password" in resp.json()["detail"].lower()
        assert await _stored(test_db, created["id"]) == (
            "MD5-Password",
            hashlib.md5(b"orig-pw").hexdigest(),
        )

    async def test_changing_type_with_new_password_stores_it_in_new_format(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_edit_retype", "MD5-Password", "orig-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "Cleartext-Password", "value": "new-pw"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] is None
        assert await _stored(test_db, created["id"]) == ("Cleartext-Password", "new-pw")

    async def test_edit_without_password_keeps_current_password(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_edit_keep", "MD5-Password", "keep-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"username": "cred_edit_keep_renamed", "attribute": "MD5-Password"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == "cred_edit_keep_renamed"
        assert await _stored(test_db, created["id"]) == (
            "MD5-Password",
            hashlib.md5(b"keep-pw").hexdigest(),
        )

    async def test_empty_password_is_rejected(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "cred_edit_empty", "Cleartext-Password", "keep-me")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"value": ""},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert await _stored(test_db, created["id"]) == ("Cleartext-Password", "keep-me")

    async def test_non_password_attribute_edit_unchanged(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "cred_edit_expiration", "Expiration", "01 Jan 2030 00:00")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"value": "02 Feb 2031 00:00"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["value"] == "02 Feb 2031 00:00"
        assert await _stored(test_db, created["id"]) == ("Expiration", "02 Feb 2031 00:00")


class TestCredentialEdgeCases:
    """Verifier findings: casing and password -> non-password conversions."""

    async def test_regression_password_attribute_casing_is_hidden(
        self, async_client, superadmin_token, helpdesk_token
    ):
        created = await _create(async_client, superadmin_token, "cred_case", "cleartext-password", "leakme")
        assert created["value"] is None
        assert created["has_password"] is True
        resp = await async_client.get("/users", headers=_auth(helpdesk_token))
        assert "leakme" not in resp.text

    async def test_regression_casing_variant_still_requires_new_password(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_case_switch", "MD5-Password", "orig-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "cleartext-password"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert await _stored(test_db, created["id"]) == (
            "MD5-Password",
            hashlib.md5(b"orig-pw").hexdigest(),
        )

    async def test_regression_password_to_non_password_requires_new_value(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "cred_to_plain", "MD5-Password", "orig-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "Expiration"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert hashlib.md5(b"orig-pw").hexdigest() not in resp.text
        assert await _stored(test_db, created["id"]) == (
            "MD5-Password",
            hashlib.md5(b"orig-pw").hexdigest(),
        )


class TestAuditLogRedaction:
    """Audit records of password rows never contain the password (#101)."""

    async def _audit_rows(self, client, token, target):
        resp = await client.get(
            "/audit/admin", params={"search": target, "limit": 100}, headers=_auth(token)
        )
        assert resp.status_code == 200, resp.text
        return [r for r in resp.json() if r["target_user"] == target]

    async def test_regression_audit_never_stores_password(
        self, async_client, superadmin_token, auditor_token
    ):
        created = await _create(async_client, superadmin_token, "cred_audit", "Cleartext-Password", "audit-secret")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "MD5-Password", "value": "audit-secret-2"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        resp = await async_client.delete(f"/users/check/{created['id']}", headers=_auth(superadmin_token))
        assert resp.status_code == 200, resp.text

        rows = await self._audit_rows(async_client, auditor_token, "cred_audit")
        assert {r["action"] for r in rows} >= {"CREATE", "UPDATE", "DELETE"}
        dumped = json.dumps(rows)
        for secret in ("audit-secret", hashlib.md5(b"audit-secret-2").hexdigest()):
            assert secret not in dumped
        assert "***" in dumped

    async def test_audit_keeps_non_password_values(self, async_client, superadmin_token, auditor_token):
        await _create(async_client, superadmin_token, "cred_audit_exp", "Expiration", "03 Mar 2032 00:00")
        rows = await self._audit_rows(async_client, auditor_token, "cred_audit_exp")
        assert "03 Mar 2032 00:00" in json.dumps(rows)


class TestNtPassword:
    """NT-Password is hashed as MD4(UTF-16LE) on create and update (#96)."""

    NT_OF_PASSWORD = "8846f7eaee8fb117ad06bdd830b7586c"  # NT hash of "password"

    async def test_create_nt_password_stores_nt_hash(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "nt_create", "NT-Password", "password")
        assert created["value"] is None
        assert created["has_password"] is True
        assert await _stored(test_db, created["id"]) == ("NT-Password", self.NT_OF_PASSWORD)

    async def test_switch_to_nt_password_with_new_password(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "nt_switch", "MD5-Password", "old-pw")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"attribute": "NT-Password", "value": "password"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert await _stored(test_db, created["id"]) == ("NT-Password", self.NT_OF_PASSWORD)

    async def test_audit_redacts_nt_password(self, async_client, superadmin_token, auditor_token):
        await _create(async_client, superadmin_token, "nt_audit", "NT-Password", "password")
        resp = await async_client.get(
            "/audit/admin", params={"search": "nt_audit"}, headers=_auth(auditor_token)
        )
        assert self.NT_OF_PASSWORD not in resp.text
        assert "password" not in json.dumps([r["new_value"] for r in resp.json()]).replace("NT-Password", "")


class TestAdminPasswordReset:
    """POST /users/check/{id}/reset-password (#101 part B)."""

    async def _reset(self, client, token, row_id, **body):
        return await client.post(
            f"/users/check/{row_id}/reset-password", json=body, headers=_auth(token)
        )

    async def test_reset_with_given_password_keeps_type(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "rst_given", "MD5-Password", "old-pw")
        resp = await self._reset(async_client, superadmin_token, created["id"], password="new-pw")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body == {"id": created["id"], "username": "rst_given", "attribute": "MD5-Password", "generated_password": None}
        assert await _stored(test_db, created["id"]) == ("MD5-Password", hashlib.md5(b"new-pw").hexdigest())

    async def test_reset_can_change_type(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "rst_type", "Cleartext-Password", "old-pw")
        resp = await self._reset(
            async_client, superadmin_token, created["id"], password="password", password_type="NT-Password"
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["attribute"] == "NT-Password"
        assert await _stored(test_db, created["id"]) == ("NT-Password", "8846f7eaee8fb117ad06bdd830b7586c")

    async def test_generated_password_is_returned_once_and_stored_hashed(
        self, async_client, superadmin_token, test_db
    ):
        from app.core.radius_passwords import nt_hash

        created = await _create(async_client, superadmin_token, "rst_gen", "NT-Password", "old-pw")
        resp = await self._reset(async_client, superadmin_token, created["id"], generate=True)
        assert resp.status_code == 200, resp.text
        generated = resp.json()["generated_password"]
        assert isinstance(generated, str) and len(generated) >= 16
        assert await _stored(test_db, created["id"]) == ("NT-Password", nt_hash(generated))

        listing = await async_client.get("/users", headers=_auth(superadmin_token))
        assert generated not in listing.text

    async def test_reset_is_audited_without_the_value(self, async_client, superadmin_token, auditor_token):
        created = await _create(async_client, superadmin_token, "rst_audit", "Cleartext-Password", "old-pw")
        resp = await self._reset(async_client, superadmin_token, created["id"], generate=True)
        generated = resp.json()["generated_password"]
        audit = await async_client.get(
            "/audit/admin", params={"search": "rst_audit"}, headers=_auth(auditor_token)
        )
        rows = [r for r in audit.json() if r["action"] == "PASSWORD_RESET"]
        assert len(rows) == 1
        assert rows[0]["admin_user"] == "test_superadmin"
        assert generated not in audit.text
        assert "Cleartext-Password" in rows[0]["new_value"]

    @pytest.mark.parametrize(
        "body, status",
        [
            ({}, 422),
            ({"password": "x", "generate": True}, 422),
            ({"password": ""}, 422),
            ({"password": "x", "password_type": "Expiration"}, 422),
        ],
    )
    async def test_invalid_requests_change_nothing(self, async_client, superadmin_token, test_db, body, status):
        created = await _create(async_client, superadmin_token, "rst_invalid", "Cleartext-Password", "keep-me")
        resp = await self._reset(async_client, superadmin_token, created["id"], **body)
        assert resp.status_code == status, resp.text
        assert await _stored(test_db, created["id"]) == ("Cleartext-Password", "keep-me")

    async def test_non_password_row_is_rejected(self, async_client, superadmin_token):
        created = await _create(async_client, superadmin_token, "rst_exp", "Expiration", "01 Jan 2030 00:00")
        resp = await self._reset(async_client, superadmin_token, created["id"], password="x")
        assert resp.status_code == 422

    async def test_unknown_row_is_404(self, async_client, superadmin_token):
        resp = await self._reset(async_client, superadmin_token, 999999, password="x")
        assert resp.status_code == 404

    @pytest.mark.parametrize("token_fixture", ["helpdesk_token", "auditor_token"])
    async def test_only_admins_can_reset(self, async_client, superadmin_token, token_fixture, request, test_db):
        created = await _create(async_client, superadmin_token, "rst_rbac", "Cleartext-Password", "keep-me")
        resp = await self._reset(async_client, request.getfixturevalue(token_fixture), created["id"], password="x")
        assert resp.status_code == 403
        assert await _stored(test_db, created["id"]) == ("Cleartext-Password", "keep-me")


class TestNonSettablePasswordTypes:
    """A password is only written under a type the backend can hash (verifier finding)."""

    async def test_regression_reset_of_crypt_row_requires_settable_type(
        self, async_client, superadmin_token, test_db
    ):
        created = await _create(async_client, superadmin_token, "crypt_reset", "Crypt-Password", "$1$abc$legacyhash")
        resp = await async_client.post(
            f"/users/check/{created['id']}/reset-password",
            json={"password": "s3cret"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert "password_type" in resp.json()["detail"]
        assert await _stored(test_db, created["id"]) == ("Crypt-Password", "$1$abc$legacyhash")

        resp = await async_client.post(
            f"/users/check/{created['id']}/reset-password",
            json={"password": "password", "password_type": "NT-Password"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert await _stored(test_db, created["id"]) == ("NT-Password", "8846f7eaee8fb117ad06bdd830b7586c")

    async def test_regression_put_value_under_crypt_is_rejected(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "crypt_put", "Crypt-Password", "$1$abc$legacyhash")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"value": "s3cret"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert await _stored(test_db, created["id"]) == ("Crypt-Password", "$1$abc$legacyhash")

    async def test_put_without_value_on_crypt_row_still_allowed(self, async_client, superadmin_token, test_db):
        created = await _create(async_client, superadmin_token, "crypt_rename", "Crypt-Password", "$1$abc$legacyhash")
        resp = await async_client.put(
            f"/users/check/{created['id']}",
            json={"username": "crypt_renamed"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert await _stored(test_db, created["id"]) == ("Crypt-Password", "$1$abc$legacyhash")
