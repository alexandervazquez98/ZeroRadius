import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_profile(async_client: AsyncClient, token: str, name: str = "gold"):
    payload = {
        "name": name,
        "downlink_high": "12000000",
        "uplink_high": "6000000",
        "downlink_low": "4000000",
        "uplink_low": "2000000",
    }
    return await async_client.post("/access-policies/bandwidth-profiles", json=payload, headers=_auth(token))


async def test_bandwidth_profile_crud(async_client: AsyncClient, superadmin_token: str):
    create_resp = await _create_profile(async_client, superadmin_token, "gold")
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "gold"

    list_resp = await async_client.get("/access-policies/bandwidth-profiles", headers=_auth(superadmin_token))
    assert list_resp.status_code == 200
    assert any(item["name"] == "gold" for item in list_resp.json())

    update_resp = await async_client.put(
        "/access-policies/bandwidth-profiles/gold",
        json={
            "name": "gold",
            "downlink_high": "13000000",
            "uplink_high": "7000000",
            "downlink_low": "5000000",
            "uplink_low": "2500000",
        },
        headers=_auth(superadmin_token),
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["downlink_high"] == "13000000"

    delete_resp = await async_client.delete(
        "/access-policies/bandwidth-profiles/gold", headers=_auth(superadmin_token)
    )
    assert delete_resp.status_code == 200


async def test_bandwidth_profile_validation_error(
    async_client: AsyncClient, superadmin_token: str
):
    invalid = {
        "name": "",
        "downlink_high": "",
        "uplink_high": "100",
        "downlink_low": "50",
        "uplink_low": "20",
    }
    resp = await async_client.post(
        "/access-policies/bandwidth-profiles", json=invalid, headers=_auth(superadmin_token)
    )
    assert resp.status_code == 422


async def test_access_policy_assignment_create_and_delete(
    async_client: AsyncClient, superadmin_token: str
):
    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Access Policy Segment", "cidr": "10.210.0.0/24"},
        headers=_auth(superadmin_token),
    )
    assert seg_resp.status_code == 201
    segment_id = seg_resp.json()["id"]

    create_1 = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "apuser",
            "segment_id": segment_id,
            "radius_group": "some_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert create_1.status_code == 201

    listed = await async_client.get(
        "/access-policies/assignments?username=apuser", headers=_auth(superadmin_token)
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 1
    assert rows[0]["radius_group"] == "some_group"

    delete_resp = await async_client.delete(
        f"/access-policies/assignments/{rows[0]['id']}", headers=_auth(superadmin_token)
    )
    assert delete_resp.status_code == 200


async def test_access_policy_preview(
    async_client: AsyncClient, superadmin_token: str
):
    await _create_profile(async_client, superadmin_token, "preview_exact")
    
    exact_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "previewuser",
            "nas_ip": "10.220.0.10",
            "radius_group": "preview_exact",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert exact_resp.status_code == 201

    preview = await async_client.post(
        "/access-policies/preview",
        json={"username": "previewuser", "nas_ip": "10.220.0.10"},
        headers=_auth(superadmin_token),
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["resolution_path"] == "exact"
    assert payload["profile"] is not None
    assert payload["profile"]["name"] == "preview_exact"


async def test_create_access_policy_bulk_ip(
    async_client: AsyncClient, superadmin_token: str
):
    payload = {
        "username": "bulkuser",
        "nas_ips": ["192.168.1.1", "192.168.1.2"],
        "radius_group": "network_admins",
        "privilege_level": "15",
    }
    response = await async_client.post("/access-policies/assignments/bulk", json=payload, headers=_auth(superadmin_token))
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["nas_ip"] == "192.168.1.1"
    assert data[1]["nas_ip"] == "192.168.1.2"
