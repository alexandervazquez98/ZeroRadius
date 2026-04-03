"""Tests A02/A07: JWT forgery — tokens manipulados deben ser rechazados."""

import pytest
import jwt as pyjwt
import base64
import json


class TestJWTSecurity:
    """Verifica que tokens JWT inválidos son rechazados."""

    async def test_jwt_wrong_secret_rejected(self, async_client):
        """Token firmado con secret incorrecto → 401."""
        fake_token = pyjwt.encode(
            {"sub": "test_superadmin", "role": "superadmin"},
            "wrong-secret-key-totally-different",
            algorithm="HS256",
        )
        resp = await async_client.get(
            "/admin-users",
            headers={"Authorization": f"Bearer {fake_token}"},
        )
        assert resp.status_code == 401

    async def test_jwt_tampered_payload_rejected(self, async_client, superadmin_token):
        """Payload modificado sin re-firmar → 401."""
        parts = superadmin_token.split(".")
        # Decode and tamper payload (add padding if needed)
        payload_padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_data = json.loads(base64.urlsafe_b64decode(payload_padded))
        payload_data["role"] = "superadmin_evil"
        new_payload = (
            base64.urlsafe_b64encode(json.dumps(payload_data).encode())
            .rstrip(b"=")
            .decode()
        )
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        resp = await async_client.get(
            "/admin-users",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert resp.status_code == 401

    async def test_no_token_rejected(self, async_client):
        """Sin token → 401."""
        resp = await async_client.get("/admin-users")
        assert resp.status_code == 401
