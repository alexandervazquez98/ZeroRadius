"""
Integration tests for MAC-based (calling_station_id) assignments and validations.
"""
import pytest
import time

@pytest.fixture
def base_mac_payload():
    return {
        "username": "mac_test_user",
        "radius_group": "cir_test_profile",
        "justification": "MAC Testing"
    }

class TestMacAssignments:
    async def test_mac_only_assignment_created(self, async_client, superadmin_token, base_mac_payload):
        payload = {**base_mac_payload, "username": "mac_test_user_only", "calling_station_id": "AA:BB:CC:DD:EE:FF"}
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["calling_station_id"] == "aabbccddeeff"
        assert data["nas_ip"] is None

    async def test_ip_and_mac_assignment_created(self, async_client, superadmin_token, base_mac_payload):
        payload = {
            **base_mac_payload,
            "username": "mac_test_user_ip",
            "nas_ip": "10.0.0.50",
            "calling_station_id": "11-22-33-44-55-66"
        }
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["calling_station_id"] == "112233445566"
        assert data["nas_ip"] == "10.0.0.50"

    async def test_mac_and_category_rejected(self, async_client, superadmin_token, base_mac_payload):
        payload = {
            **base_mac_payload,
            "calling_station_id": "AABBCCDDEEFF",
            "nas_category_id": 1
        }
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422
        assert "exactly one targeting method required" in resp.text.lower() or "method required" in resp.text.lower()

    async def test_ip_mac_and_category_rejected(self, async_client, superadmin_token, base_mac_payload):
        payload = {
            **base_mac_payload,
            "nas_ip": "10.0.0.50",
            "calling_station_id": "AABBCCDDEEFF",
            "nas_category_id": 1
        }
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422
        assert "ip+mac targeting cannot be combined with category or segment" in resp.text.lower()

    async def test_invalid_mac_format_rejected(self, async_client, superadmin_token, base_mac_payload):
        payload = {
            **base_mac_payload,
            "calling_station_id": "invalid-mac-format"
        }
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422
        assert "invalid mac address format" in resp.text.lower()

    @pytest.mark.parametrize("mac_input, expected_normalized", [
        ("00:11:22:33:44:55", "001122334455"),
        ("AA-BB-CC-DD-EE-FF", "aabbccddeeff"),
        ("aabb.ccdd.eeff", "aabbccddeeff"),
        ("AABBCCDDEEFF", "aabbccddeeff"),
    ])
    async def test_mac_formats_normalized(self, async_client, superadmin_token, base_mac_payload, mac_input, expected_normalized):
        payload = {**base_mac_payload, "username": f"mac_test_{expected_normalized}_{int(time.time()*1000)}", "calling_station_id": mac_input}
        resp = await async_client.post(
            "/privilege-map/category",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["calling_station_id"] == expected_normalized
