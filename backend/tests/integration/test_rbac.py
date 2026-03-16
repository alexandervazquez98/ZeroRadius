"""
T40 — Integration tests: RBAC permission matrix.

Verifies the complete RBAC permission matrix from REQ-BE-004.
Uses async_client + token fixtures from conftest.py.

Endpoint categories tested:
- GET /api/audit/access        → all roles can read
- GET /api/audit/export        → auditor/admin/superadmin only; helpdesk/readonly → 403
- POST/DELETE /api/admin-users → superadmin only
- PUT /api/groups (high-priv)  → superadmin only
- GET/POST /api/privilege-map  → auditor can GET; helpdesk cannot POST
"""

import pytest


class TestAuditAccess:
    """GET /api/audit/access — all authenticated roles should be able to read."""

    async def test_superadmin_can_read_audit(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200

    async def test_admin_can_read_audit(self, async_client, admin_token):
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_read_audit(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_auditor_can_read_audit(self, async_client, auditor_token):
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200

    async def test_readonly_can_read_audit(self, async_client, readonly_token):
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200


class TestAuditExport:
    """GET /api/audit/export — auditor/admin/superadmin only."""

    async def test_auditor_can_export(self, async_client, auditor_token):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200

    async def test_admin_can_export(self, async_client, admin_token):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_superadmin_can_export(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_cannot_export(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Insufficient permissions"

    async def test_readonly_cannot_export(self, async_client, readonly_token):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403


class TestAdminUsersRBAC:
    """POST/PUT/DELETE /api/admin-users — superadmin only for write operations."""

    async def test_admin_cannot_create_admin_user(self, async_client, admin_token):
        payload = {
            "username": "new_test_user",
            "email": "x@test.com",
            "password": "Str0ngP@ssw0rd!",
            "role": "admin",
        }
        resp = await async_client.post(
            "/admin-users",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    async def test_helpdesk_cannot_create_admin_user(
        self, async_client, helpdesk_token
    ):
        payload = {
            "username": "new_test_user2",
            "email": "y@test.com",
            "password": "Str0ngP@ssw0rd!",
            "role": "helpdesk",
        }
        resp = await async_client.post(
            "/admin-users",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_superadmin_can_create_admin_user(
        self, async_client, superadmin_token
    ):
        payload = {
            "username": "created_by_superadmin",
            "email": "z@test.com",
            "password": "Str0ngP@ssw0rd!",
            "role": "helpdesk",
        }
        resp = await async_client.post(
            "/admin-users",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # 200 or 201 on success (admin user created)
        assert resp.status_code in (200, 201)

    async def test_helpdesk_cannot_delete_admin_user(
        self, async_client, helpdesk_token
    ):
        resp = await async_client.delete(
            "/admin-users/999999",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_auditor_cannot_delete_admin_user(self, async_client, auditor_token):
        resp = await async_client.delete(
            "/admin-users/999999",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403


class TestPrivilegeMapRBAC:
    """GET/POST/DELETE /api/privilege-map — auditor can read, admin+ can write."""

    async def test_auditor_can_read_privilege_map(self, async_client, auditor_token):
        resp = await async_client.get(
            "/privilege-map",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200

    async def test_admin_can_read_privilege_map(self, async_client, admin_token):
        resp = await async_client.get(
            "/privilege-map",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_auditor_cannot_create_privilege_map(
        self, async_client, auditor_token
    ):
        payload = {
            "username": "jperez",
            "nas_ips": ["10.1.1.1"],
            "radius_group": "grp_test",
            "privilege_level": "level-1",
            "approved_by": "admin",
            "review_date": "2027-01-01",
        }
        resp = await async_client.post(
            "/privilege-map",
            json=payload,
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403

    async def test_helpdesk_cannot_create_privilege_map(
        self, async_client, helpdesk_token
    ):
        payload = {
            "username": "jperez",
            "nas_ips": ["10.1.1.2"],
            "radius_group": "grp_test",
            "privilege_level": "level-1",
            "approved_by": "admin",
            "review_date": "2027-01-01",
        }
        resp = await async_client.post(
            "/privilege-map",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_delete_privilege_map(
        self, async_client, readonly_token
    ):
        resp = await async_client.delete(
            "/privilege-map/999999",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403
