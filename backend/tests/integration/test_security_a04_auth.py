"""Tests A04: password policy, force_change middleware, JIT TTL max."""

import pytest


class TestPasswordPolicy:
    """Verifica que la política de contraseñas rechaza passwords débiles."""

    async def test_password_too_short_rejected(self, async_client, superadmin_token):
        """Password nueva < 12 chars → 422."""
        resp = await async_client.post(
            "/auth/change-password",
            json={"old_password": "TestPassword1!", "new_password": "Short1!"},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422

    async def test_password_no_special_rejected(self, async_client, superadmin_token):
        """Password nueva sin carácter especial → 422."""
        resp = await async_client.post(
            "/auth/change-password",
            json={"old_password": "TestPassword1!", "new_password": "NoSpecial12345"},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422

    async def test_password_valid_accepted(self, async_client, superadmin_token):
        """Password válida (12+ chars, mayúscula, dígito, especial) → no 422.

        Puede retornar 400 si el old_password no coincide con el hash actual
        (el usuario ya cambió su password en otra parte del test suite),
        pero lo importante es que la validación de complejidad NO se dispare (422).
        """
        resp = await async_client.post(
            "/auth/change-password",
            json={"old_password": "TestPassword1!", "new_password": "Secure@Pass123"},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # 200 OK o 400 (old_password incorrecto) — pero NO 422 (policy check pasó)
        assert resp.status_code != 422


class TestForceChangeMiddleware:
    """Verifica que el middleware de force_change bloquea endpoints normales."""

    async def test_force_change_blocks_regular_endpoint(self, async_client):
        """Token con force_change=True → 403 en endpoints normales."""
        from app.core.security import create_access_token

        force_token = create_access_token(
            data={"sub": "test_superadmin", "role": "superadmin", "force_change": True}
        )
        resp = await async_client.get(
            "/users",
            headers={"Authorization": f"Bearer {force_token}"},
        )
        assert resp.status_code == 403

    async def test_force_change_allows_change_password(self, async_client):
        """Token con force_change=True → el middleware permite pasar a /auth/change-password."""
        from app.core.security import create_access_token

        force_token = create_access_token(
            data={"sub": "test_superadmin", "role": "superadmin", "force_change": True}
        )
        resp = await async_client.post(
            "/auth/change-password",
            json={
                "old_password": "TestPassword1!",
                "new_password": "NewSecure@Pass123",
            },
            headers={"Authorization": f"Bearer {force_token}"},
        )
        # El middleware debe permitir pasar — puede ser 200 o 400 (wrong old_password),
        # pero NO debe ser 403 (bloqueado por el middleware force_change)
        assert resp.status_code != 403


class TestJITTTLMax:
    """Verifica la validación de TTL máximo en JIT approvals."""

    async def test_jit_ttl_max_exceeded(self, async_client, superadmin_token):
        """ttl_hours > 168 → 422 (Query validator ge=1, le=168)."""
        resp = await async_client.post(
            "/users/jit-requests/someuser/approve?ttl_hours=169",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422

    async def test_jit_ttl_max_ok(self, async_client, superadmin_token):
        """ttl_hours=168 → no 422 (puede ser 404 si user no existe)."""
        resp = await async_client.post(
            "/users/jit-requests/nonexistent_user/approve?ttl_hours=168",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code != 422
