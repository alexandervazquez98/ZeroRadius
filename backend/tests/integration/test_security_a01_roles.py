"""Tests A01: Access Control — roles en endpoints sensibles."""

import pytest


class TestAdminUsersRoles:
    """Verifica que /admin-users restringe acceso por rol."""

    async def test_admin_users_readonly_forbidden(self, async_client, readonly_token):
        resp = await async_client.get(
            "/admin-users",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_admin_users_admin_ok(self, async_client, admin_token):
        resp = await async_client.get(
            "/admin-users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestAuditRoles:
    """Verifica que los endpoints de auditoría restringen acceso por rol."""

    async def test_audit_admin_readonly_forbidden(self, async_client, readonly_token):
        resp = await async_client.get(
            "/audit/admin",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_audit_admin_auditor_ok(self, async_client, auditor_token):
        resp = await async_client.get(
            "/audit/admin",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200

    async def test_audit_access_any_role_ok(self, async_client, readonly_token):
        """GET /audit/access está disponible para todos los roles autenticados
        (fuente de verdad: test_rbac.py — todos los roles pueden leer access logs)."""
        resp = await async_client.get(
            "/audit/access",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200


class TestSessionsRoles:
    """Verifica que /sessions restringe acceso por rol."""

    async def test_sessions_active_any_role_ok(self, async_client, readonly_token):
        """GET /sessions/active está disponible para todos los roles autenticados
        (fuente de verdad: test_sessions.py — helpdesk y readonly pueden leer)."""
        resp = await async_client.get(
            "/sessions/active",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200

    async def test_sessions_disconnect_readonly_forbidden(
        self, async_client, readonly_token
    ):
        """POST /sessions/{u}/disconnect requiere ADMIN/SUPERADMIN."""
        resp = await async_client.post(
            "/sessions/anyuser/disconnect?framed_ip=1.2.3.4",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_sessions_active_admin_ok(self, async_client, admin_token):
        resp = await async_client.get(
            "/sessions/active",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200


class TestUsersCheckRoles:
    """Verifica que /users/check restringe PUT y DELETE a roles privilegiados."""

    async def test_users_check_put_readonly_forbidden(
        self, async_client, readonly_token
    ):
        resp = await async_client.put(
            "/users/check/9999",
            json={"attribute": "Cleartext-Password", "op": ":=", "value": "test"},
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_users_check_delete_readonly_forbidden(
        self, async_client, readonly_token
    ):
        resp = await async_client.delete(
            "/users/check/9999",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403


class TestDictionaryLogsRoles:
    """Verifica que /dictionary/radius-logs restringe acceso a ADMIN/SUPERADMIN."""

    async def test_radius_logs_readonly_forbidden(self, async_client, readonly_token):
        resp = await async_client.get(
            "/dictionary/radius-logs",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_radius_logs_admin_ok(self, async_client, admin_token):
        resp = await async_client.get(
            "/dictionary/radius-logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 200 OK (logs vacíos o unavailable) — lo importante es que NO sea 403
        assert resp.status_code != 403
