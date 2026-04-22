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


async def test_regression_cross_area_like_segment_isolation_by_distinct_cidrs(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    area_a_segment = await async_client.post(
        "/network-segments",
        json={"name": "Area-A Shared Name", "cidr": "10.160.0.0/24"},
        headers=headers,
    )
    area_b_segment = await async_client.post(
        "/network-segments",
        json={"name": "Area-B Shared Name", "cidr": "10.161.0.0/24"},
        headers=headers,
    )

    assert area_a_segment.status_code == 201
    assert area_b_segment.status_code == 201

    area_a_id = area_a_segment.json()["id"]
    area_b_id = area_b_segment.json()["id"]

    map_a = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "segment_admin_a",
            "segment_id": area_a_id,
            "radius_group": "area_a_group",
        },
        headers=headers,
    )
    map_b = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "segment_reader_b",
            "segment_id": area_b_id,
            "radius_group": "area_b_group",
        },
        headers=headers,
    )
    assert map_a.status_code == 201
    assert map_b.status_code == 201

    list_a = await async_client.get("/privilege-map?username=segment_admin_a", headers=headers)
    list_b = await async_client.get("/privilege-map?username=segment_reader_b", headers=headers)
    assert list_a.status_code == 200
    assert list_b.status_code == 200

    segment_names_a = {item["segment_name"] for item in list_a.json() if item["segment_name"]}
    segment_names_b = {item["segment_name"] for item in list_b.json() if item["segment_name"]}
    assert "Area-A Shared Name" in segment_names_a
    assert "Area-A Shared Name" not in segment_names_b
    assert "Area-B Shared Name" in segment_names_b
    assert "Area-B Shared Name" not in segment_names_a


async def test_regression_deterministic_user_segment_match_and_no_match_paths(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    segment = await async_client.post(
        "/network-segments",
        json={"name": "Deterministic Match Segment", "cidr": "10.162.0.0/24"},
        headers=headers,
    )
    assert segment.status_code == 201
    segment_id = segment.json()["id"]

    mapping = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "matchpathuser",
            "segment_id": segment_id,
            "radius_group": "deterministic_match_group",
        },
        headers=headers,
    )
    assert mapping.status_code == 201

    list_match = await async_client.get(
        "/privilege-map?username=matchpathuser", headers=headers
    )
    list_no_match = await async_client.get(
        "/privilege-map?username=nomatchuser", headers=headers
    )
    assert list_match.status_code == 200
    assert list_no_match.status_code == 200

    assert any(
        row["radius_group"] == "deterministic_match_group" for row in list_match.json()
    )
    assert len(list_no_match.json()) == 0
