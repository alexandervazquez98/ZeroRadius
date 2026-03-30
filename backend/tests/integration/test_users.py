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
