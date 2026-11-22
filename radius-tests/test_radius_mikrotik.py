"""
MikroTik support (#99, #96).

Relies on `radius-tests/fixtures/seed_mikrotik.sql`:

- `mt.nt` is stored as NT-Password (MD4 of UTF-16LE), the format the backend
  writes for MikroTik users. PAP must accept it.
- The policy group `mikrotik-full` replies `Mikrotik-Group := full`, which
  FreeRADIUS can only encode when `backend/dictionaries/dictionary.mikrotik`
  is loaded (the radius image strips the upstream vendor dictionary).

MS-CHAP against NT-Password is not covered here (pyrad has no MS-CHAP
client). `radtest -t mschap` checks MS-CHAP v1 by hand (see
docs/01-nas-provisioning.md); MS-CHAPv2 is exercised by a real RouterOS.
"""

import pytest
from pyrad import packet

from conftest import parse_reply_attributes, reply_contains_marker, send_access_request

pytestmark = pytest.mark.radius

MIKROTIK_NAS = "192.0.2.30"


class TestMikrotik:
    @pytest.mark.radius
    def test_nt_password_user_gets_mikrotik_group(self, radius_client, skip_if_no_radius):
        reply = send_access_request(
            radius_client, username="mt.nt", password="testpassword", nas_ip=MIKROTIK_NAS
        )

        assert reply.code == packet.AccessAccept, f"Expected Access-Accept, got code {reply.code}"
        assert reply_contains_marker(reply, "MIKROTIK-FULL")
        attrs = parse_reply_attributes(reply)
        assert attrs.get("Mikrotik-Group") == ["full"], (
            f"Mikrotik-Group missing from Access-Accept (dictionary.mikrotik loaded?): {attrs}"
        )

    @pytest.mark.radius
    def test_nt_password_wrong_password_is_rejected(self, radius_client, skip_if_no_radius):
        reply = send_access_request(
            radius_client, username="mt.nt", password="wrong-password", nas_ip=MIKROTIK_NAS
        )

        assert reply.code == packet.AccessReject, f"Expected Access-Reject, got code {reply.code}"
        assert "Mikrotik-Group" not in parse_reply_attributes(reply)
