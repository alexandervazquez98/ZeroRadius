"""Message-Authenticator echo contract (RFC 3579 section 3.2).

When a NAS signs its Access-Request with Message-Authenticator, the
reply (Access-Accept or Access-Reject) must carry a valid
Message-Authenticator too. MikroTik RouterOS (v6 and v7) drops unsigned
replies to signed requests ("received packet ... with missing message
auth, dropping"), so a correct Access-Accept still ends in a login
timeout. FreeRADIUS 3.2.3 only adds it for EAP; ZeroRadius adds it in
`radius/default.conf` post-auth.

NAS that do not sign requests (Cisco IOS PAP) must keep receiving
unsigned replies: the previous behavior is pinned by
`test_unsigned_request_gets_unsigned_reply`.

The packets are built by hand (raw UDP) instead of with pyrad so the
test controls the request signature and verifies the reply HMAC
byte-for-byte, independent of pyrad's Message-Authenticator support.

Seed: `radius-tests/fixtures/seed_huntgroup_enforcement.sql`
(`juan.perez` / `testpassword`, accepted from NAS-IP 192.168.1.10).
"""

import hashlib
import hmac
import os
import socket
import struct

import pytest

from conftest import RADIUS_HOST, RADIUS_PORT, RADIUS_SECRET

pytestmark = pytest.mark.radius

ACCESS_REQUEST = 1
ACCESS_ACCEPT = 2
ACCESS_REJECT = 3

ATTR_USER_NAME = 1
ATTR_USER_PASSWORD = 2
ATTR_NAS_IP_ADDRESS = 4
ATTR_MESSAGE_AUTHENTICATOR = 80

ZERO_MA = b"\x00" * 16


def _attr(attr_type: int, value: bytes) -> bytes:
    return struct.pack("!BB", attr_type, len(value) + 2) + value


def _pap_encrypt(password: str, secret: bytes, authenticator: bytes) -> bytes:
    data = password.encode()
    data += b"\x00" * (-len(data) % 16 or 0)
    if not data:
        data = b"\x00" * 16
    result, last = b"", authenticator
    for i in range(0, len(data), 16):
        digest = hashlib.md5(secret + last).digest()
        block = bytes(a ^ b for a, b in zip(data[i : i + 16], digest))
        result += block
        last = block
    return result


def _iter_attrs(attrs: bytes):
    offset = 0
    while offset < len(attrs):
        attr_type, length = attrs[offset], attrs[offset + 1]
        yield offset, attr_type, attrs[offset + 2 : offset + length]
        offset += length


def _send(username: str, password: str, nas_ip: str, sign: bool):
    """Send one Access-Request; return (request_authenticator, reply_bytes)."""
    packet_id = os.urandom(1)[0]
    authenticator = os.urandom(16)
    attrs = (
        _attr(ATTR_USER_NAME, username.encode())
        + _attr(ATTR_USER_PASSWORD, _pap_encrypt(password, RADIUS_SECRET, authenticator))
        + _attr(ATTR_NAS_IP_ADDRESS, socket.inet_aton(nas_ip))
    )
    if sign:
        attrs += _attr(ATTR_MESSAGE_AUTHENTICATOR, ZERO_MA)
    header = struct.pack("!BBH", ACCESS_REQUEST, packet_id, 20 + len(attrs))
    raw = header + authenticator + attrs
    if sign:
        mac = hmac.new(RADIUS_SECRET, raw, hashlib.md5).digest()
        raw = raw[:-16] + mac

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(3)
        sock.sendto(raw, (RADIUS_HOST, RADIUS_PORT))
        reply, _ = sock.recvfrom(4096)

    assert reply[1] == packet_id, "reply id does not match request id"
    return authenticator, reply


def _assert_response_authenticator(reply: bytes, request_authenticator: bytes):
    expected = hashlib.md5(
        reply[:4] + request_authenticator + reply[20:] + RADIUS_SECRET
    ).digest()
    assert reply[4:20] == expected, "Response Authenticator is invalid (wrong secret?)"


def _message_authenticator(reply: bytes):
    """Return (offset_in_packet, value) of Message-Authenticator, or None."""
    for offset, attr_type, value in _iter_attrs(reply[20:]):
        if attr_type == ATTR_MESSAGE_AUTHENTICATOR:
            return 20 + offset, value
    return None


def _assert_valid_message_authenticator(reply: bytes, request_authenticator: bytes):
    found = _message_authenticator(reply)
    assert found is not None, (
        "reply to a signed request has no Message-Authenticator; "
        "MikroTik drops it with 'missing message auth'"
    )
    offset, value = found
    assert len(value) == 16, f"Message-Authenticator must be 16 bytes, got {len(value)}"
    zeroed = (
        reply[:4]
        + request_authenticator
        + reply[20 : offset + 2]
        + ZERO_MA
        + reply[offset + 18 :]
    )
    expected = hmac.new(RADIUS_SECRET, zeroed, hashlib.md5).digest()
    assert value == expected, "reply Message-Authenticator HMAC is invalid"


class TestMessageAuthenticatorEcho:
    def test_signed_request_gets_signed_access_accept(self, skip_if_no_radius):
        req_auth, reply = _send("juan.perez", "testpassword", "192.168.1.10", sign=True)

        assert reply[0] == ACCESS_ACCEPT, f"expected Access-Accept, got code {reply[0]}"
        _assert_response_authenticator(reply, req_auth)
        _assert_valid_message_authenticator(reply, req_auth)

    def test_signed_request_gets_signed_access_reject(self, skip_if_no_radius):
        req_auth, reply = _send("juan.perez", "wrong-password", "192.168.1.10", sign=True)

        assert reply[0] == ACCESS_REJECT, f"expected Access-Reject, got code {reply[0]}"
        _assert_response_authenticator(reply, req_auth)
        _assert_valid_message_authenticator(reply, req_auth)

    def test_unsigned_request_gets_unsigned_reply(self, skip_if_no_radius):
        """Previous behavior (Cisco IOS PAP): no Message-Authenticator added."""
        req_auth, reply = _send("juan.perez", "testpassword", "192.168.1.10", sign=False)

        assert reply[0] == ACCESS_ACCEPT, f"expected Access-Accept, got code {reply[0]}"
        _assert_response_authenticator(reply, req_auth)
        assert _message_authenticator(reply) is None, (
            "unsigned request unexpectedly got a Message-Authenticator in the reply"
        )
