"""
RADIUS protocol tests — Access-Request / Access-Accept / Access-Reject.

Requiere un servidor FreeRADIUS activo. Todos los tests están marcados con
@pytest.mark.radius y usan el fixture skip_if_no_radius para auto-skipear
si el servidor no responde.

Para correr:
    pytest radius-tests/ (requiere FreeRADIUS activo)

Para excluir del suite principal:
    pytest backend/ -m "not radius"

Ver README.md para instrucciones de cómo levantar FreeRADIUS con Docker.
"""

import pytest
from pyrad import packet
from pyrad.client import Timeout

pytestmark = pytest.mark.radius

# ---------------------------------------------------------------------------
# Credenciales de test — deben existir en el FreeRADIUS de test
# ---------------------------------------------------------------------------
VALID_USER = "testuser"
VALID_PASS = "testpassword"
WRONG_PASS = "wrongpassword_xyz"
UNKNOWN_USER = "ghost_user_that_does_not_exist"


def _send_access_request(client, username: str, password: str):
    """Construye y envía un Access-Request, retorna el paquete de respuesta."""
    req = client.CreateAuthPacket(
        code=packet.AccessRequest,
        User_Name=username,
    )
    req["User-Password"] = req.PwCrypt(password)
    req["NAS-IP-Address"] = "127.0.0.1"
    req["NAS-Port"] = 0
    return client.SendPacket(req)


class TestAccessRequestAccept:
    """Access-Request con credenciales válidas → Access-Accept (code=2)."""

    @pytest.mark.radius
    def test_valid_credentials_produce_accept(self, radius_client, skip_if_no_radius):
        """Usuario y contraseña correctos reciben Access-Accept."""
        try:
            reply = _send_access_request(radius_client, VALID_USER, VALID_PASS)
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept (2), got code {reply.code}"
        )


class TestAccessRequestReject:
    """Access-Request con credenciales inválidas → Access-Reject (code=3)."""

    @pytest.mark.radius
    def test_wrong_password_produces_reject(self, radius_client, skip_if_no_radius):
        """Contraseña incorrecta para usuario existente recibe Access-Reject."""
        try:
            reply = _send_access_request(radius_client, VALID_USER, WRONG_PASS)
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject (3), got code {reply.code}"
        )

    @pytest.mark.radius
    def test_unknown_user_produces_reject(self, radius_client, skip_if_no_radius):
        """Usuario inexistente recibe Access-Reject."""
        try:
            reply = _send_access_request(radius_client, UNKNOWN_USER, "anypassword")
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject (3) for unknown user, got code {reply.code}"
        )

    @pytest.mark.radius
    def test_empty_password_produces_reject(self, radius_client, skip_if_no_radius):
        """Contraseña vacía es rechazada."""
        try:
            reply = _send_access_request(radius_client, VALID_USER, "")
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessReject
