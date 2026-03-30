"""
Integration tests: /auth/token endpoint.

Verifies:
- Successful login returns 200 + access_token
- Invalid password returns 401
- Empty body returns 422
"""

import pytest


class TestAuthLogin:
    """POST /auth/token — OAuth2 password flow."""

    async def test_login_success_returns_jwt(self, async_client):
        """Valid credentials produce a JWT access token."""
        resp = await async_client.post(
            "/auth/token",
            data={"username": "test_superadmin", "password": "TestPassword1!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_invalid_password_returns_401(self, async_client):
        """Wrong password is rejected."""
        resp = await async_client.post(
            "/auth/token",
            data={"username": "test_superadmin", "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Incorrect username or password"

    async def test_login_unknown_user_returns_401(self, async_client):
        """Nonexistent username is rejected."""
        resp = await async_client.post(
            "/auth/token",
            data={"username": "ghost_user_xyz", "password": "AnyPassword!"},
        )
        assert resp.status_code == 401

    async def test_login_empty_body_returns_422(self, async_client):
        """Missing form fields produce a validation error."""
        resp = await async_client.post("/auth/token", data={})
        assert resp.status_code == 422
