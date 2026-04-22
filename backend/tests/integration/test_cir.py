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
    return await async_client.post("/cir/profiles", json=payload, headers=_auth(token))


async def test_cir_profile_crud(async_client: AsyncClient, superadmin_token: str):
    create_resp = await _create_profile(async_client, superadmin_token, "gold")
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "gold"

    list_resp = await async_client.get("/cir/profiles", headers=_auth(superadmin_token))
    assert list_resp.status_code == 200
    assert any(item["name"] == "gold" for item in list_resp.json())

    update_resp = await async_client.put(
        "/cir/profiles/gold",
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
        "/cir/profiles/gold", headers=_auth(superadmin_token)
    )
    assert delete_resp.status_code == 200


async def test_cir_profile_validation_error_keeps_field_context(
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
        "/cir/profiles", json=invalid, headers=_auth(superadmin_token)
    )
    assert resp.status_code == 422
    body = resp.json()
    assert "detail" in body


async def test_cir_assignment_create_replace_and_delete(
    async_client: AsyncClient, superadmin_token: str
):
    await _create_profile(async_client, superadmin_token, "bronze")
    await _create_profile(async_client, superadmin_token, "silver")

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "CIR Segment", "cidr": "10.210.0.0/24"},
        headers=_auth(superadmin_token),
    )
    assert seg_resp.status_code == 201
    segment_id = seg_resp.json()["id"]

    create_1 = await async_client.post(
        "/cir/assignments",
        json={
            "username": "ciruser",
            "segment_id": segment_id,
            "radius_group": "cir_bronze",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert create_1.status_code == 201

    create_2 = await async_client.post(
        "/cir/assignments",
        json={
            "username": "ciruser",
            "segment_id": segment_id,
            "radius_group": "cir_silver",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert create_2.status_code == 201
    assert create_2.json()["radius_group"] == "cir_silver"

    listed = await async_client.get(
        "/cir/assignments?username=ciruser", headers=_auth(superadmin_token)
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["radius_group"] == "cir_silver"

    delete_resp = await async_client.delete(
        f"/cir/assignments/{rows[0]['id']}", headers=_auth(superadmin_token)
    )
    assert delete_resp.status_code == 200


async def test_cir_preview_exact_wins_and_no_match(
    async_client: AsyncClient, superadmin_token: str
):
    await _create_profile(async_client, superadmin_token, "preview_exact")
    await _create_profile(async_client, superadmin_token, "preview_segment")

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Preview Segment", "cidr": "10.220.0.0/24"},
        headers=_auth(superadmin_token),
    )
    assert seg_resp.status_code == 201
    segment_id = seg_resp.json()["id"]

    exact_resp = await async_client.post(
        "/cir/assignments",
        json={
            "username": "previewuser",
            "nas_ip": "10.220.0.10",
            "radius_group": "cir_preview_exact",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert exact_resp.status_code == 201

    segment_resp = await async_client.post(
        "/cir/assignments",
        json={
            "username": "previewuser",
            "segment_id": segment_id,
            "radius_group": "cir_preview_segment",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert segment_resp.status_code == 201

    preview = await async_client.post(
        "/cir/preview",
        json={"username": "previewuser", "nas_ip": "10.220.0.10"},
        headers=_auth(superadmin_token),
    )
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["resolution_path"] == "exact"
    assert payload["profile"]["name"] == "preview_exact"
    assert len(payload["trace"]) >= 2

    no_match = await async_client.post(
        "/cir/preview",
        json={"username": "missing-user", "nas_ip": "10.220.0.99"},
        headers=_auth(superadmin_token),
    )
    assert no_match.status_code == 200
    assert no_match.json()["resolution_path"] == "none"


async def test_cir_rbac_readonly_behavior(
    async_client: AsyncClient,
    superadmin_token: str,
    admin_token: str,
    auditor_token: str,
    readonly_token: str,
):
    create_admin = await _create_profile(async_client, admin_token, "rbac_admin")
    assert create_admin.status_code == 201

    list_auditor = await async_client.get("/cir/profiles", headers=_auth(auditor_token))
    assert list_auditor.status_code == 200

    preview_auditor = await async_client.post(
        "/cir/preview",
        json={"username": "nobody", "nas_ip": "10.10.10.10"},
        headers=_auth(auditor_token),
    )
    assert preview_auditor.status_code == 200

    create_readonly = await _create_profile(async_client, readonly_token, "forbidden")
    assert create_readonly.status_code == 403

    delete_admin = await async_client.delete(
        "/cir/profiles/rbac_admin", headers=_auth(admin_token)
    )
    assert delete_admin.status_code == 403

    delete_superadmin = await async_client.delete(
        "/cir/profiles/rbac_admin", headers=_auth(superadmin_token)
    )
    assert delete_superadmin.status_code == 200
