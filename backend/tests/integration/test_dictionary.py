"""
Integration tests: /dictionary endpoint.

Verifies:
- Any authenticated role can list dictionary files (GET /dictionary/files)
- Any authenticated role can query attributes (GET /dictionary/attributes)
- Unauthenticated requests are rejected
"""

import pytest


class TestDictionaryRead:
    """GET /dictionary/files and /dictionary/attributes — authenticated access."""

    async def test_superadmin_can_list_dictionary_files(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_list_dictionary_files(self, async_client, admin_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_list_dictionary_files(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_readonly_can_list_dictionary_files(self, async_client, readonly_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200

    async def test_superadmin_can_list_attributes(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/dictionary/attributes",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_unauthenticated_cannot_list_dictionary_files(self, async_client):
        resp = await async_client.get("/dictionary/files")
        assert resp.status_code in (401, 403)

    async def test_unauthenticated_cannot_list_attributes(self, async_client):
        resp = await async_client.get("/dictionary/attributes")
        assert resp.status_code in (401, 403)
