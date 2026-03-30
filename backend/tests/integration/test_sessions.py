"""
Integration tests: /sessions/active endpoint.

Verifies:
- Any authenticated role can read active sessions (returns 200 + list)
- Unauthenticated requests are rejected
"""

import pytest


class TestSessionsRead:
    """GET /sessions/active — all authenticated roles."""

    async def test_superadmin_can_read_sessions(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/sessions/active",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_helpdesk_can_read_sessions(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/sessions/active",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_readonly_can_read_sessions(self, async_client, readonly_token):
        resp = await async_client.get(
            "/sessions/active",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200

    async def test_unauthenticated_cannot_read_sessions(self, async_client):
        resp = await async_client.get("/sessions/active")
        assert resp.status_code in (401, 403)
