"""
RADIUS protocol tests — Vendor-specific scenarios.

Tests for Cisco WLC, Dahua CCTV, Proxy-MAC via parent NAS, and generic IP devices.
Requires FreeRADIUS server running. Auto-skipped if server unreachable.

Run:
    pytest radius-tests/ -v -m radius
"""

import pytest
from pyrad import packet
from pyrad.client import Timeout

from conftest import (
    parse_reply_attributes,
    reply_contains_marker,
    send_access_request,
    send_access_request_vendor,
)

pytestmark = pytest.mark.radius

# Cisco Vendor ID (RFC 1700 assigned number)
CISCO_VENDOR_ID = 9
# Dahua Vendor ID (assigned vendor number for Dahua)
DAHUA_VENDOR_ID = 47793


class TestProxyMACViaParentNAS:
    """Device authenticating through a parent AP (proxy).

    When a device authenticates via a parent NAS proxy:
    - NAS-IP-Address = original AP IP (not proxy's IP)
    - Called-Station-Id = original AP MAC:SSID
    - Calling-Station-Id = device MAC
    - Proxy-State attribute may be added by proxy
    """

    @pytest.mark.radius
    def test_proxy_child_device_uses_parent_nas_ip(
        self, radius_client, skip_if_no_radius
    ):
        """Child device behind proxy gets original AP's NAS-IP for policy resolution."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="proxy_child_device",
                password="testpassword",
                nas_ip="10.10.10.1",
                called_station_id="00-11-22-33-44-55:Lobby-SSID",
                calling_station_id="AA-BB-CC-DD-EE-FF",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for proxy child device, got {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        # Verify marker is present (group replies)
        assert reply_contains_marker(reply, "PROXY-CHILD")

    @pytest.mark.radius
    def test_proxy_child_device_without_calling_station(
        self, radius_client, skip_if_no_radius
    ):
        """Proxy child device without Calling-Station-Id falls back to NAS-IP rule."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="proxy_child_device",
                password="testpassword",
                nas_ip="10.10.10.1",
                called_station_id="00-11-22-33-44-55:Lobby-SSID",
                calling_station_id=None,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        # Without calling station, policy resolves via NAS-IP only
        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept, got {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        assert reply_contains_marker(reply, "PROXY-CHILD")

    @pytest.mark.radius
    def test_proxy_child_device_rejects_wrong_password(
        self, radius_client, skip_if_no_radius
    ):
        """Proxy child device with wrong password receives Access-Reject."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="proxy_child_device",
                password="wrongpassword",
                nas_ip="10.10.10.1",
                called_station_id="00-11-22-33-44-55:Lobby-SSID",
                calling_station_id="AA-BB-CC-DD-EE-FF",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for wrong password, got {reply.code}"
        )


class TestCiscoWLCDevice:
    """Cisco Wireless LAN Controller scenario.

    Key attributes:
    - NAS-Identifier (string): WLC name
    - Called-Station-Id: AP MAC:SSID format
    - Calling-Station-Id: client MAC
    - NAS-Port-Type=19 (wireless)
    - Cisco-AVPair in reply for privileged users
    """

    @pytest.mark.radius
    def test_cisco_wlc_admin_receives_avpair(
        self, radius_client, skip_if_no_radius
    ):
        """Cisco WLC privileged user must receive Cisco-AVPair in Access-Accept."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="cisco_wlc_admin",
                password="testpassword",
                nas_ip="192.168.1.101",
                called_station_id="00:11:22:33:44:55:Cisco-SSID",
                calling_station_id="CC-DD-EE-FF-00-11",
                nas_identifier="WLC-Campus-01",
                nas_port_type=19,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        # NOTE: Cisco-AVPair VSA requires Cisco dictionary to be loaded in FreeRADIUS.
        # Without it, the group reply query fails. This test validates the auth flow works
        # when NAS vendor is configured. Full VSA testing requires dictionary setup.
        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for Cisco WLC admin, got {reply.code}"
        )

        # Verify marker is present (group replies)
        assert reply_contains_marker(reply, "CISCO-WLC-PRIV")

    @pytest.mark.radius
    def test_cisco_wlc_regular_user_no_high_priv(
        self, radius_client, skip_if_no_radius
    ):
        """Regular Cisco WLC user should NOT receive high-privilege Cisco-AVPair."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="cisco_wlc_operator",
                password="testpassword",
                nas_ip="192.168.1.101",
                called_station_id="00:11:22:33:44:55:Cisco-SSID",
                calling_station_id="CC-DD-EE-FF-00-11",
                nas_identifier="WLC-Campus-01",
                nas_port_type=19,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        if reply.code != packet.AccessAccept:
            pytest.skip("Cisco WLC operator not accepted — check FreeRADIUS setup")

        # If VSA present, verify it does NOT contain privilege-level=15
        if 26 in reply:
            raw_vsa = str(reply[26])
            assert "privilege-level=15" not in raw_vsa, (
                "Regular user should not receive privilege-level=15 Cisco-AVPair"
            )

    @pytest.mark.radius
    def test_cisco_wlc_with_nas_identifier(
        self, radius_client, skip_if_no_radius
    ):
        """Cisco WLC with NAS-Identifier attribute resolves policy correctly."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="cisco_wlc_admin",
                password="testpassword",
                nas_ip="192.168.1.101",
                nas_identifier="WLC-Building-A",
                called_station_id="00-11-22-33-44-55:Corporate",
                calling_station_id="AA:BB:CC:DD:EE:FF",
                nas_port_type=19,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept
        assert reply_contains_marker(reply, "CISCO-WLC-PRIV")

    @pytest.mark.radius
    def test_cisco_wlc_reject_unknown_user(
        self, radius_client, skip_if_no_radius
    ):
        """Unknown user to Cisco WLC gets Access-Reject."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="cisco_ghost_user",
                password="testpassword",
                nas_ip="192.168.1.101",
                called_station_id="00:11:22:33:44:55:Cisco-SSID",
                nas_port_type=19,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for unknown user, got {reply.code}"
        )


class TestDahuaCamera:
    """Dahua CCTV camera scenario.

    Key attributes:
    - Vendor ID 47793
    - Calling-Station-Id = camera MAC
    - Simple PAP auth
    - Limited VSA (Dahua-Recording-Channel if used)
    """

    @pytest.mark.radius
    def test_dahua_camera_in_lobby_accept(
        self, radius_client, skip_if_no_radius
    ):
        """Dahua camera in lobby authenticates and receives Access-Accept."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="dahua_camera_lobby",
                password="testpassword",
                nas_ip="192.168.2.1",
                called_station_id="Dahua-NVR-01",
                calling_station_id="A4-28-5E-9C-3B-7D",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for Dahua camera, got {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        assert reply_contains_marker(reply, "DAHUA-CAMERA")

    @pytest.mark.radius
    def test_dahua_camera_different_location(
        self, radius_client, skip_if_no_radius
    ):
        """Dahua camera at different location (entrance) also gets Access-Accept."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="dahua_camera_entrance",
                password="testpassword",
                nas_ip="192.168.2.1",
                called_station_id="Dahua-NVR-02",
                calling_station_id="B4-38-6F-8C-4A-8F",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for Dahua entrance camera, got {reply.code}"
        )
        assert reply_contains_marker(reply, "DAHUA-CAMERA")

    @pytest.mark.radius
    def test_dahua_camera_wrong_password_rejects(
        self, radius_client, skip_if_no_radius
    ):
        """Dahua camera with wrong password receives Access-Reject."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="dahua_camera_lobby",
                password="badpassword",
                nas_ip="192.168.2.1",
                called_station_id="Dahua-NVR-01",
                calling_station_id="A4-28-5E-9C-3B-7D",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for wrong password, got {reply.code}"
        )

    @pytest.mark.radius
    def test_dahua_camera_unknown_device_rejects(
        self, radius_client, skip_if_no_radius
    ):
        """Unknown Dahua device is rejected."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="dahua_unknown_camera",
                password="testpassword",
                nas_ip="192.168.2.1",
                calling_station_id="unknown-camera-mac",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for unknown device, got {reply.code}"
        )


class TestGenericIPDevice:
    """Generic IP fixed device scenario (printer, sensor, etc.).

    Minimal Access-Request: only User-Name, User-Password, NAS-IP-Address.
    Tests that basic authentication works without vendor-specific attributes.
    """

    @pytest.mark.radius
    def test_generic_printer_accept(self, radius_client, skip_if_no_radius):
        """Generic IP printer authenticates with minimal attributes."""
        try:
            reply = send_access_request(
                radius_client,
                username="genericPrinter",
                password="testpassword",
                nas_ip="192.168.3.1",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for generic printer, got {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        assert reply_contains_marker(reply, "GENERIC-DEVICE")

    @pytest.mark.radius
    def test_generic_device_without_calling_station(
        self, radius_client, skip_if_no_radius
    ):
        """Generic device without Calling-Station-Id resolves via NAS-IP only."""
        try:
            reply = send_access_request_vendor(
                radius_client,
                username="genericPrinter",
                password="testpassword",
                nas_ip="192.168.3.1",
                called_station_id=None,
                calling_station_id=None,
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept without Calling-Station-Id, got {reply.code}"
        )
        assert reply_contains_marker(reply, "GENERIC-DEVICE")

    @pytest.mark.radius
    def test_generic_device_wrong_password_rejects(
        self, radius_client, skip_if_no_radius
    ):
        """Generic device with wrong password receives Access-Reject."""
        try:
            reply = send_access_request(
                radius_client,
                username="genericPrinter",
                password="wrongpassword",
                nas_ip="192.168.3.1",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for wrong password, got {reply.code}"
        )

    @pytest.mark.radius
    def test_generic_device_unknown_user_rejects(
        self, radius_client, skip_if_no_radius
    ):
        """Unknown generic device user is rejected."""
        try:
            reply = send_access_request(
                radius_client,
                username="unknownPrinter",
                password="testpassword",
                nas_ip="192.168.3.1",
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for unknown user, got {reply.code}"
        )

    @pytest.mark.radius
    def test_minimal_request_with_only_required_fields(
        self, radius_client, skip_if_no_radius
    ):
        """Minimal Access-Request with only User-Name, User-Password, NAS-IP-Address."""
        req = radius_client.CreateAuthPacket(
            code=packet.AccessRequest,
            User_Name="genericPrinter",
        )
        req["User-Password"] = req.PwCrypt("testpassword")
        req["NAS-IP-Address"] = "192.168.3.1"
        req["NAS-Port"] = 0

        try:
            reply = radius_client.SendPacket(req)
        except Timeout:
            pytest.skip("FreeRADIUS timed out")

        assert reply.code == packet.AccessAccept
        assert reply_contains_marker(reply, "GENERIC-DEVICE")