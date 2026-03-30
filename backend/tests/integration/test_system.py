"""
Integration tests: root / and /system/ntp-status endpoints.

Verifies:
- GET / is public and returns 200 with a welcome message
- GET /system/ntp-status requires admin or superadmin
- helpdesk cannot access ntp-status (403)
"""

import pytest


class TestRootEndpoint:
    """GET / — public health check."""

    async def test_root_returns_200(self, async_client):
        resp = await async_client.get("/")
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestSystemNTPStatus:
    """GET /system/ntp-status — admin/superadmin only."""

    async def test_superadmin_can_read_ntp_status(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # 200 if ntpd/chrony is available; service may return 200 even without
        # an actual NTP daemon (ntp_status service handles gracefully)
        assert resp.status_code == 200

    async def test_admin_can_read_ntp_status(self, async_client, admin_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_cannot_read_ntp_status(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_read_ntp_status(self, async_client, readonly_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_read_ntp_status(self, async_client):
        resp = await async_client.get("/system/ntp-status")
        assert resp.status_code in (401, 403)
