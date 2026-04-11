from httpx import AsyncClient


async def test_regression_delete_segment_blocked_when_exception_ranges_exist(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    segment_resp = await async_client.post(
        "/network-segments",
        json={"name": "Delete Guard Segment", "cidr": "10.110.0.0/16"},
        headers=headers,
    )
    assert segment_resp.status_code == 201
    segment_id = segment_resp.json()["id"]

    exception_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "deleteguarduser",
            "segment_id": segment_id,
            "target_start_ip": "10.110.1.10",
            "target_end_ip": "10.110.1.20",
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert exception_resp.status_code == 201

    delete_resp = await async_client.delete(
        f"/network-segments/{segment_id}", headers=headers
    )
    assert delete_resp.status_code == 409
    assert (
        delete_resp.json()["detail"]
        == "Cannot delete network segment while dependent privilege maps exist"
    )


async def test_regression_delete_segment_blocked_when_base_policy_exists(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    segment_resp = await async_client.post(
        "/network-segments",
        json={"name": "Delete Base Guard Segment", "cidr": "10.115.0.0/16"},
        headers=headers,
    )
    assert segment_resp.status_code == 201
    segment_id = segment_resp.json()["id"]

    mapping_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "deletebaseguarduser",
            "segment_id": segment_id,
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert mapping_resp.status_code == 201

    delete_resp = await async_client.delete(
        f"/network-segments/{segment_id}", headers=headers
    )
    assert delete_resp.status_code == 409
    assert (
        delete_resp.json()["detail"]
        == "Cannot delete network segment while dependent privilege maps exist"
    )


async def test_regression_update_segment_rejected_when_exception_would_be_out_of_bounds(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    segment_resp = await async_client.post(
        "/network-segments",
        json={"name": "Update Guard Segment", "cidr": "10.111.0.0/16"},
        headers=headers,
    )
    assert segment_resp.status_code == 201
    segment_id = segment_resp.json()["id"]

    exception_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "updateguarduser",
            "segment_id": segment_id,
            "target_start_ip": "10.111.1.10",
            "target_end_ip": "10.111.1.20",
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert exception_resp.status_code == 201

    update_resp = await async_client.put(
        f"/network-segments/{segment_id}",
        json={"cidr": "10.111.0.0/24"},
        headers=headers,
    )
    assert update_resp.status_code == 409
    assert "dependent exception" in update_resp.json()["detail"]
    assert "10.111.1.10-10.111.1.20" in update_resp.json()["detail"]


async def test_regression_create_network_segment_rejects_overlapping_cidr(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    first_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Base Segment", "cidr": "10.112.0.0/16"},
        headers=headers,
    )
    assert first_resp.status_code == 201

    second_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Child Segment", "cidr": "10.112.1.0/24"},
        headers=headers,
    )
    assert second_resp.status_code == 409
    assert "overlaps with existing segment" in second_resp.json()["detail"]


async def test_regression_update_network_segment_rejects_overlapping_cidr(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    first_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Update Base", "cidr": "10.113.0.0/16"},
        headers=headers,
    )
    assert first_resp.status_code == 201

    second_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Update Candidate", "cidr": "10.114.0.0/16"},
        headers=headers,
    )
    assert second_resp.status_code == 201
    second_id = second_resp.json()["id"]

    update_resp = await async_client.put(
        f"/network-segments/{second_id}",
        json={"cidr": "10.113.128.0/17"},
        headers=headers,
    )
    assert update_resp.status_code == 409
    assert "overlaps with existing segment" in update_resp.json()["detail"]
