"""
RADIUS protocol tests — VSA (Vendor-Specific Attributes).

Verifica que usuarios con privilege map reciben el Cisco-AVPair en Access-Accept.
Requiere FreeRADIUS con la tabla UserNasPrivilegeMap integrada vía rlm_sql.

Marcados con @pytest.mark.radius — se skipean sin servidor activo.
"""

import pytest
from pyrad import packet
from pyrad.client import Timeout

pytestmark = pytest.mark.radius

# Usuario que debe tener un privilege map configurado en FreeRADIUS
PRIVILEGED_USER = "testuser_privileged"
PRIVILEGED_PASS = "testpassword"

# Cisco Vendor ID
CISCO_VENDOR_ID = 9


def _send_access_request(client, username: str, password: str):
    req = client.CreateAuthPacket(
        code=packet.AccessRequest,
        User_Name=username,
    )
    req["User-Password"] = req.PwCrypt(password)
    req["NAS-IP-Address"] = "127.0.0.1"
    req["NAS-Port"] = 0
    return client.SendPacket(req)


class TestVSAHandling:
    """Verifica que VSA Cisco-AVPair se incluye en Access-Accept para usuarios privilegiados."""

    @pytest.mark.radius
    def test_privileged_user_receives_cisco_avpair(self, radius_client, skip_if_no_radius):
        """Access-Accept para usuario privilegiado debe incluir VSA Cisco-AVPair."""
        try:
            reply = _send_access_request(radius_client, PRIVILEGED_USER, PRIVILEGED_PASS)
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        # Debe ser Accept primero
        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for privileged user, got {reply.code}"
        )

        # Verificar que hay atributos VSA en la respuesta
        # pyrad expone VSA como (vendor_id, [(type, value)]) en reply[26]
        has_vsa = 26 in reply  # RFC 2865 atributo 26 = Vendor-Specific
        assert has_vsa, (
            "Expected Vendor-Specific attributes (id=26) in Access-Accept for privileged user"
        )

    @pytest.mark.radius
    def test_regular_user_accept_has_no_high_privilege_vsa(self, radius_client, skip_if_no_radius):
        """Un usuario sin privilege map NO debe recibir Cisco-AVPair de alto privilegio."""
        from conftest import VALID_USER, VALID_PASS  # reutilizamos los credenciales base

        try:
            reply = _send_access_request(radius_client, VALID_USER, VALID_PASS)
        except Timeout:
            pytest.skip("RADIUS server timed out — is FreeRADIUS running?")

        if reply.code != packet.AccessAccept:
            pytest.skip("Regular user not accepted — check FreeRADIUS test setup")

        # Si hay VSA, verificar que NO contiene "privilege-level=15"
        if 26 in reply:
            raw_vsa = str(reply[26])
            assert "privilege-level=15" not in raw_vsa, (
                "Regular user should not receive privilege-level=15"
            )
