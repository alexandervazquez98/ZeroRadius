"""
Integration tests: /nas endpoint.

Verifies:
- Any authenticated role can list NAS devices (GET /nas)
- Only superadmin/admin can create NAS (POST /nas)
- helpdesk / readonly cannot create NAS (403)
- Unauthenticated requests are rejected
"""

import pytest

# A valid NAS secret must be ≥ 32 characters (enforced by NasCreate schema)
_VALID_SECRET = "a" * 32


class TestNasRead:
    """GET /nas — list NAS devices."""

    async def test_superadmin_can_list_nas(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_list_nas(self, async_client, admin_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_list_nas(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {helpdesk_token}"}
        )
        assert resp.status_code == 200

    async def test_unauthenticated_cannot_list_nas(self, async_client):
        resp = await async_client.get("/nas")
        assert resp.status_code in (401, 403)


class TestNasCreate:
    """POST /nas — create NAS (superadmin/admin only)."""

    async def test_superadmin_can_create_nas(self, async_client, superadmin_token):
        payload = {
            "nasname": "10.99.99.1",
            "shortname": "test-nas-superadmin",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # NAS router may fail if Docker is not available (_reload_radius),
        # but the DB write succeeds — 200/201 expected
        assert resp.status_code in (200, 201)

    async def test_admin_can_create_nas(self, async_client, admin_token):
        payload = {
            "nasname": "10.99.99.2",
            "shortname": "test-nas-admin",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code in (200, 201)

    async def test_helpdesk_cannot_create_nas(self, async_client, helpdesk_token):
        payload = {
            "nasname": "10.99.99.3",
            "shortname": "test-nas-helpdesk",
            "secret": _VALID_SECRET,
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_create_nas(self, async_client, readonly_token):
        payload = {
            "nasname": "10.99.99.4",
            "shortname": "test-nas-readonly",
            "secret": _VALID_SECRET,
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_nas_secret_too_short_returns_422(self, async_client, superadmin_token):
        """NAS secret < 32 chars must be rejected by the schema validator."""
        payload = {
            "nasname": "10.99.99.5",
            "shortname": "test-nas-short-secret",
            "secret": "tooshort",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422
