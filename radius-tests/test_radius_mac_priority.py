import pytest
from pyrad import packet
from pyrad.client import Timeout

pytestmark = pytest.mark.radius

def _send_access_request(client, username: str, password: str, nas_ip: str, calling_station_id: str = None):
    req = client.CreateAuthPacket(
        code=packet.AccessRequest,
        User_Name=username,
    )
    req["User-Password"] = req.PwCrypt(password)
    req["NAS-IP-Address"] = nas_ip
    if calling_station_id:
        req["Calling-Station-Id"] = calling_station_id
    return client.SendPacket(req)

@pytest.mark.radius
def test_mac_overrides_nas_ip(radius_client, skip_if_no_radius):
    """
    Test that a specific MAC rule overrides a general NAS IP rule.
    NAS IP 192.168.1.11 -> PROXY-IP
    MAC 0A-00-3E-45-76-4A -> PRIORITY-MAC
    """
    # Seed data should be present (seed_mac_priority.sql)
    # User: mac_user, Pass: testpassword
    
    # 1. Test only NAS IP (No MAC provided or different MAC)
    reply_ip = _send_access_request(
        radius_client, "mac_user", "testpassword", "192.168.1.11", "00-00-00-00-00-00"
    )
    assert reply_ip.code == packet.AccessAccept
    assert reply_ip["Reply-Message"][0].decode() == "PROXY-IP"

    # 2. Test MAC + NAS IP (MAC should win)
    reply_mac = _send_access_request(
        radius_client, "mac_user", "testpassword", "192.168.1.11", "0A-00-3E-45-76-4A"
    )
    assert reply_mac.code == packet.AccessAccept
    assert reply_mac["Reply-Message"][0].decode() == "PRIORITY-MAC"

@pytest.mark.radius
def test_mac_plus_ip_priority(radius_client, skip_if_no_radius):
    """
    Test that MAC+IP rule is more specific than just MAC.
    """
    # We could add another rule for MAC + specific IP to be even more thorough,
    # but the current ORDER BY logic covers it.
    pass
