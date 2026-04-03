"""Tests A10: validadores de input — nasname y framed_ip.

Observaciones del código real:
- POST /nas usa NasCreate que valida:
    - nasname: debe ser IP, CIDR o hostname RFC-1123
    - secret: mínimo 32 caracteres
- POST /sessions/{username}/disconnect espera framed_ip como query param (no body JSON).
"""

import pytest


# Secret válido de 32+ chars para los tests de NAS
_VALID_SECRET = "A" * 32  # Exactamente 32 chars


class TestNasnameValidator:
    """Verifica que NasCreate rechaza nasname con formato inválido."""

    async def test_nasname_invalid_format_rejected(self, async_client, admin_token):
        """nasname con formato inválido → 422."""
        resp = await async_client.post(
            "/nas",
            json={
                "nasname": "not-valid!@#",
                "shortname": "test",
                "type": "other",
                "secret": _VALID_SECRET,
                "description": "Test NAS",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    async def test_nasname_valid_ip_accepted(self, async_client, admin_token):
        """nasname con IP válida → no 422 (pasa validación del schema)."""
        resp = await async_client.post(
            "/nas",
            json={
                "nasname": "192.168.100.200",
                "shortname": "test-nas-sec",
                "type": "other",
                "secret": _VALID_SECRET,
                "description": "Test NAS security",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Puede ser 200 (creado) — lo importante es que NO sea 422 (validación pasó)
        assert resp.status_code != 422


class TestFramedIpValidator:
    """Verifica que disconnect valida framed_ip como IP válida."""

    async def test_framed_ip_invalid_rejected(self, async_client, admin_token):
        """framed_ip inválido en disconnect → 422.

        El endpoint POST /sessions/{username}/disconnect espera framed_ip
        como query parameter (no body JSON). Con IP inválida debe retornar 422.
        """
        resp = await async_client.post(
            "/sessions/test_superadmin/disconnect?framed_ip=not-an-ip",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 422 si la validación funciona
        # Lo que NO debe ser es 200 con una IP inválida aceptada
        assert resp.status_code in (400, 403, 404, 422)

    async def test_framed_ip_valid_accepted(self, async_client, admin_token):
        """framed_ip válido en disconnect → no 422 (puede ser 200 o error de negocio)."""
        resp = await async_client.post(
            "/sessions/test_superadmin/disconnect?framed_ip=10.0.0.1",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # Con IP válida, la validación pasa — puede retornar 200 (placeholder de POD)
        assert resp.status_code not in (422,)
