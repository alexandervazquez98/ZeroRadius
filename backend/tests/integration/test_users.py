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
