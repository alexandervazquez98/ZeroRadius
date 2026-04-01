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

    async def test_superadmin_can_list_group_replies(
        self, async_client, superadmin_token
    ):
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

    async def test_superadmin_can_create_group_reply(
        self, async_client, superadmin_token
    ):
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

    async def test_helpdesk_cannot_create_group_reply(
        self, async_client, helpdesk_token
    ):
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

    async def test_readonly_cannot_create_group_check(
        self, async_client, readonly_token
    ):
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

    async def test_helpdesk_cannot_delete_group_reply(
        self, async_client, helpdesk_token
    ):
        resp = await async_client.delete(
            "/groups/reply/999999",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_auditor_cannot_delete_group_policy(
        self, async_client, auditor_token
    ):
        resp = await async_client.delete(
            "/groups/policy?groupname=nonexistent_group",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403


class TestGroupsUpdate:
    """PUT /groups/reply/{id} and PUT /groups/check/{id} — superadmin/admin only."""

    async def test_superadmin_can_update_group_reply(
        self, async_client, superadmin_token
    ):
        # First create a reply
        create_payload = {
            "groupname": "test_update_reply",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "NAS-Prompt-User",
        }
        create_resp = await async_client.post(
            "/groups/reply",
            json=create_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert create_resp.status_code in (200, 201)
        created_id = create_resp.json()["id"]

        # Now update it
        update_payload = {
            "groupname": "test_update_reply",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "Administrative-User",
        }
        update_resp = await async_client.put(
            f"/groups/reply/{created_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["value"] == "Administrative-User"

    async def test_helpdesk_cannot_update_group_reply(
        self, async_client, helpdesk_token
    ):
        update_payload = {
            "groupname": "test_update_reply",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "Administrative-User",
        }
        resp = await async_client.put(
            "/groups/reply/1",
            json=update_payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_superadmin_can_update_group_check(
        self, async_client, superadmin_token
    ):
        # First create a check
        create_payload = {
            "groupname": "test_update_check",
            "attribute": "NAS-IP-Address",
            "op": "==",
            "value": "10.0.0.1",
        }
        create_resp = await async_client.post(
            "/groups/check",
            json=create_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert create_resp.status_code in (200, 201)
        created_id = create_resp.json()["id"]

        # Now update it
        update_payload = {
            "groupname": "test_update_check",
            "attribute": "NAS-IP-Address",
            "op": "==",
            "value": "10.0.0.2",
        }
        update_resp = await async_client.put(
            f"/groups/check/{created_id}",
            json=update_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["value"] == "10.0.0.2"

    async def test_readonly_cannot_update_group_check(
        self, async_client, readonly_token
    ):
        update_payload = {
            "groupname": "test_update_check",
            "attribute": "NAS-IP-Address",
            "op": "==",
            "value": "10.0.0.2",
        }
        resp = await async_client.put(
            "/groups/check/1",
            json=update_payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403


class TestGroupsManagement:
    """Group management endpoints: rename and by-name."""

    async def test_get_group_by_name(self, async_client, superadmin_token):
        # First create a reply
        create_payload = {
            "groupname": "test_mgmt_group",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "NAS-Prompt-User",
        }
        await async_client.post(
            "/groups/reply",
            json=create_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

        # Now get it by name
        resp = await async_client.get(
            "/groups/by-name/test_mgmt_group",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["groupname"] == "test_mgmt_group"
        assert len(data["replies"]) == 1
        assert data["replies"][0]["attribute"] == "Service-Type"

    async def test_rename_group(self, async_client, superadmin_token):
        # First create a reply
        create_payload = {
            "groupname": "test_old_name",
            "attribute": "Service-Type",
            "op": ":=",
            "value": "NAS-Prompt-User",
        }
        await async_client.post(
            "/groups/reply",
            json=create_payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

        # Now rename it
        resp = await async_client.put(
            "/groups/rename?old_groupname=test_old_name&new_groupname=test_new_name",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert "renamed" in resp.json()["message"]

        # Verify it's gone under old name
        get_resp = await async_client.get(
            "/groups/by-name/test_old_name",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert get_resp.status_code == 404

        # Verify it exists under new name
        get_resp2 = await async_client.get(
            "/groups/by-name/test_new_name",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert get_resp2.status_code == 200
        assert get_resp2.json()["groupname"] == "test_new_name"

    async def test_helpdesk_cannot_rename_group(self, async_client, helpdesk_token):
        resp = await async_client.put(
            "/groups/rename?old_groupname=test&new_groupname=test2",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403
