"""
Integration tests: /groups endpoint (radgroupreply, radgroupcheck, radusergroup).

Verifies:
- Any authenticated role can list group replies and checks (GET)
- Only superadmin/admin can create/delete (RBAC enforced)
- helpdesk cannot create or delete group attributes (403)
"""

import pytest


class TestGroupsRead:
    """GET /groups/reply and /groups/check — readable by all roles."""

    async def test_superadmin_can_list_group_replies(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/groups/reply",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_helpdesk_can_list_group_replies(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/groups/reply",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_readonly_can_list_group_checks(self, async_client, readonly_token):
        resp = await async_client.get(
            "/groups/check",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200

    async def test_unauthenticated_cannot_list_groups(self, async_client):
        resp = await async_client.get("/groups/reply")
        assert resp.status_code in (401, 403)

    async def test_any_role_can_list_groups_list(self, async_client, auditor_token):
        """GET /groups/list returns distinct group names."""
        resp = await async_client.get(
            "/groups/list",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestGroupsCreate:
    """POST /groups/reply — superadmin/admin only."""

    async def test_superadmin_can_create_group_reply(self, async_client, superadmin_token):
        payload = {
            "groupname": "test_grp_integration",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "NAS-Prompt-User",
        }
        resp = await async_client.post(
            "/groups/reply",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code in (200, 201)

    async def test_helpdesk_cannot_create_group_reply(self, async_client, helpdesk_token):
        payload = {
            "groupname": "test_grp_helpdesk",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "NAS-Prompt-User",
        }
        resp = await async_client.post(
            "/groups/reply",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_create_group_check(self, async_client, readonly_token):
        payload = {
            "groupname": "test_grp_readonly",
            "attribute": "Auth-Type",
            "op": ":=",
            "value": "PAP",
        }
        resp = await async_client.post(
            "/groups/check",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403


class TestGroupsDelete:
    """DELETE /groups/reply/{id} — superadmin/admin only."""

    async def test_helpdesk_cannot_delete_group_reply(self, async_client, helpdesk_token):
        resp = await async_client.delete(
            "/groups/reply/999999",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_auditor_cannot_delete_group_policy(self, async_client, auditor_token):
        resp = await async_client.delete(
            "/groups/policy?groupname=nonexistent_group",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403
