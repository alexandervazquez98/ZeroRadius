import ipaddress

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _resolve_expected_rule(nas_ip: str, exact_ip: str, range_cidr: str, base_cidr: str) -> str:
    ip = ipaddress.ip_address(nas_ip)
    if ip == ipaddress.ip_address(exact_ip):
        return "exact"
    if ip in ipaddress.ip_network(range_cidr):
        return "range"
    if ip in ipaddress.ip_network(base_cidr):
        return "base"
    return "fallback"


async def test_create_privilege_map_bulk_ip(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload = {
        "username": "testuser",
        "nas_ips": ["192.168.1.1", "192.168.1.2"],
        "radius_group": "network_admins",
        "privilege_level": "15",
    }
    response = await async_client.post("/privilege-map", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["nas_ip"] == "192.168.1.1"
    assert data[0]["nas_category_id"] is None
    assert data[1]["nas_ip"] == "192.168.1.2"


async def test_create_privilege_map_category(
    async_client: AsyncClient, admin_token: str, superadmin_token: str
):
    headers_sa = {"Authorization": f"Bearer {superadmin_token}"}
    # 1. Create a category first
    cat_payload = {"name": "Test Map Category", "criticality": "critical"}
    cat_resp = await async_client.post(
        "/nas-categories", json=cat_payload, headers=headers_sa
    )
    cat_id = cat_resp.json()["id"]

    # 2. Create privilege map targeting the category using admin token
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "username": "catuser",
        "nas_category_id": cat_id,
        "radius_group": "fw_admins",
        "privilege_level": "7",
    }
    response = await async_client.post(
        "/privilege-map/category", json=payload, headers=headers_admin
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "catuser"
    assert data["nas_ip"] is None
    assert data["nas_category_id"] == cat_id
    assert data["nas_category_name"] == "Test Map Category"
    assert data["radius_group"] == "fw_admins"


async def test_create_privilege_map_category_missing_id(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload = {
        "username": "failuser",
        "radius_group": "fw_admins",
        "privilege_level": "7",
        # missing nas_category_id and nas_ip
    }
    response = await async_client.post(
        "/privilege-map/category", json=payload, headers=headers
    )
    assert response.status_code == 422


async def test_create_privilege_map_category_unauthorized(
    async_client: AsyncClient, readonly_token: str
):
    headers = {"Authorization": f"Bearer {readonly_token}"}
    payload = {
        "username": "catuser2",
        "nas_category_id": 1,
        "radius_group": "fw_admins",
    }
    response = await async_client.post(
        "/privilege-map/category", json=payload, headers=headers
    )
    assert response.status_code == 403


async def test_list_privilege_maps(
    async_client: AsyncClient, superadmin_token: str, auditor_token: str
):
    headers_sa = {"Authorization": f"Bearer {superadmin_token}"}

    # 1. Create a map
    payload = {
        "username": "listuser",
        "nas_ips": ["10.0.0.1"],
        "radius_group": "list_group",
    }
    await async_client.post("/privilege-map", json=payload, headers=headers_sa)

    # 2. List with auditor token
    headers_auditor = {"Authorization": f"Bearer {auditor_token}"}
    response = await async_client.get(
        "/privilege-map?username=listuser", headers=headers_auditor
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["username"] == "listuser"


async def test_update_privilege_map(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # 1. Create category and map
    cat_resp = await async_client.post(
        "/nas-categories",
        json={"name": "Update Cat", "criticality": "standard"},
        headers=headers,
    )
    cat_id = cat_resp.json()["id"]

    map_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "updateme",
            "nas_category_id": cat_id,
            "radius_group": "initial_group",
        },
        headers=headers,
    )
    map_id = map_resp.json()["id"]

    # 2. Update map
    update_payload = {
        "username": "updateme",
        "nas_category_id": cat_id,
        "radius_group": "new_group",
        "privilege_level": "99",
    }
    update_resp = await async_client.put(
        f"/privilege-map/{map_id}", json=update_payload, headers=headers
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["radius_group"] == "new_group"
    assert data["privilege_level"] == "99"


async def test_delete_privilege_map(
    async_client: AsyncClient, superadmin_token: str, admin_token: str
):
    headers_sa = {"Authorization": f"Bearer {superadmin_token}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create map
    map_resp = await async_client.post(
        "/privilege-map",
        json={
            "username": "deleteme",
            "nas_ips": ["10.1.1.1"],
            "radius_group": "delete_group",
        },
        headers=headers_sa,
    )
    map_id = map_resp.json()[0]["id"]

    # 2. Admin cannot delete (only superadmin)
    del_admin_resp = await async_client.delete(
        f"/privilege-map/{map_id}", headers=headers_admin
    )
    assert del_admin_resp.status_code == 403

    # 3. Superadmin can delete
    del_sa_resp = await async_client.delete(
        f"/privilege-map/{map_id}", headers=headers_sa
    )
    assert del_sa_resp.status_code == 200

    # 4. Verify deleted
    get_resp = await async_client.get(
        f"/privilege-map?username=deleteme", headers=headers_sa
    )
    assert len(get_resp.json()) == 0


async def test_create_privilege_map_segment_overlap(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # 1. Create a segment
    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Test Seg", "cidr": "10.100.0.0/16"},
        headers=headers,
    )
    assert seg_resp.status_code == 201
    seg_id = seg_resp.json()["id"]

    # 2. Create first exception
    exc1_payload = {
        "username": "overlapuser",
        "segment_id": seg_id,
        "target_start_ip": "10.100.1.10",
        "target_end_ip": "10.100.1.20",
        "radius_group": "group1",
    }
    resp1 = await async_client.post(
        "/privilege-map/category", json=exc1_payload, headers=headers
    )
    assert resp1.status_code == 201

    # 3. Create overlapping exception
    exc2_payload = {
        "username": "overlapuser",
        "segment_id": seg_id,
        "target_start_ip": "10.100.1.15",
        "target_end_ip": "10.100.1.25",
        "radius_group": "group2",
    }
    resp2 = await async_client.post(
        "/privilege-map/category", json=exc2_payload, headers=headers
    )
    assert resp2.status_code == 422
    assert "overlaps" in resp2.json()["detail"]

    # 4. Create non-overlapping exception
    exc3_payload = {
        "username": "overlapuser",
        "segment_id": seg_id,
        "target_start_ip": "10.100.1.21",
        "target_end_ip": "10.100.1.30",
        "radius_group": "group3",
    }
    resp3 = await async_client.post(
        "/privilege-map/category", json=exc3_payload, headers=headers
    )
    assert resp3.status_code == 201

    # 5. Create out of bounds exception
    exc4_payload = {
        "username": "overlapuser",
        "segment_id": seg_id,
        "target_start_ip": "10.200.1.1",
        "target_end_ip": "10.200.1.10",
        "radius_group": "group4",
    }
    resp4 = await async_client.post(
        "/privilege-map/category", json=exc4_payload, headers=headers
    )
    assert resp4.status_code == 422
    assert "strictly fall within" in resp4.json()["detail"]


async def test_regression_segment_policy_requires_existing_segment(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    create_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "missingsegment",
            "segment_id": 999999,
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert create_resp.status_code == 404
    assert create_resp.json()["detail"] == "Network segment not found"

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Existing Segment For Update", "cidr": "10.102.0.0/16"},
        headers=headers,
    )
    seg_id = seg_resp.json()["id"]

    map_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "validsegment",
            "segment_id": seg_id,
            "radius_group": "group1",
        },
        headers=headers,
    )
    map_id = map_resp.json()["id"]

    update_resp = await async_client.put(
        f"/privilege-map/{map_id}",
        json={
            "username": "validsegment",
            "segment_id": 999999,
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert update_resp.status_code == 404
    assert update_resp.json()["detail"] == "Network segment not found"


async def test_regression_duplicate_base_segment_mapping_rejected_before_commit(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Base Duplicate Segment", "cidr": "10.103.0.0/16"},
        headers=headers,
    )
    seg_id = seg_resp.json()["id"]

    first_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "dupbaseuser",
            "segment_id": seg_id,
            "radius_group": "group1",
        },
        headers=headers,
    )
    assert first_resp.status_code == 201

    second_resp = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "dupbaseuser",
            "segment_id": seg_id,
            "radius_group": "group2",
        },
        headers=headers,
    )
    assert second_resp.status_code == 409
    assert (
        second_resp.json()["detail"]
        == "A base policy for this user and network segment already exists"
    )


async def test_update_privilege_map_segment_overlap(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Overlap Update Seg", "cidr": "10.101.0.0/16"},
        headers=headers,
    )
    seg_id = seg_resp.json()["id"]

    resp1 = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "upoverlapuser",
            "segment_id": seg_id,
            "target_start_ip": "10.101.1.10",
            "target_end_ip": "10.101.1.20",
            "radius_group": "group1",
        },
        headers=headers,
    )

    resp2 = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "upoverlapuser",
            "segment_id": seg_id,
            "target_start_ip": "10.101.1.30",
            "target_end_ip": "10.101.1.40",
            "radius_group": "group2",
        },
        headers=headers,
    )
    map2_id = resp2.json()["id"]

    # update map2 to overlap with map1
    up_resp = await async_client.put(
        f"/privilege-map/{map2_id}",
        json={
            "username": "upoverlapuser",
            "segment_id": seg_id,
            "target_start_ip": "10.101.1.15",
            "target_end_ip": "10.101.1.35",
            "radius_group": "group2",
        },
        headers=headers,
    )
    assert up_resp.status_code == 422
    assert "overlaps" in up_resp.json()["detail"]

    # update map2 without overlap
    up_resp_ok = await async_client.put(
        f"/privilege-map/{map2_id}",
        json={
            "username": "upoverlapuser",
            "segment_id": seg_id,
            "target_start_ip": "10.101.1.25",
            "target_end_ip": "10.101.1.40",
            "radius_group": "group2",
        },
        headers=headers,
    )
    assert up_resp_ok.status_code == 200


async def test_regression_precedence_matrix_rows_created_for_multi_user_same_segment(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Matrix Shared Segment", "cidr": "10.150.0.0/24"},
        headers=headers,
    )
    assert seg_resp.status_code == 201
    segment_id = seg_resp.json()["id"]

    cat_resp = await async_client.post(
        "/nas-categories",
        json={"name": "Matrix Fallback Category", "criticality": "standard"},
        headers=headers,
    )
    assert cat_resp.status_code == 201
    category_id = cat_resp.json()["id"]

    cases = [
        {
            "username": "segment_admin_a",
            "payload": {
                "username": "segment_admin_a",
                "nas_ip": "10.150.0.50",
                "radius_group": "matrix_exact_a",
            },
            "expected_rule": "exact",
        },
        {
            "username": "segment_admin_a",
            "payload": {
                "username": "segment_admin_a",
                "segment_id": segment_id,
                "target_start_ip": "10.150.0.60",
                "target_end_ip": "10.150.0.69",
                "radius_group": "matrix_range_a",
            },
            "expected_rule": "range",
        },
        {
            "username": "segment_admin_a",
            "payload": {
                "username": "segment_admin_a",
                "segment_id": segment_id,
                "radius_group": "matrix_base_a",
            },
            "expected_rule": "base",
        },
        {
            "username": "segment_admin_a",
            "payload": {
                "username": "segment_admin_a",
                "nas_category_id": category_id,
                "radius_group": "matrix_fallback_a",
            },
            "expected_rule": "fallback",
        },
        {
            "username": "segment_reader_b",
            "payload": {
                "username": "segment_reader_b",
                "segment_id": segment_id,
                "target_start_ip": "10.150.0.70",
                "target_end_ip": "10.150.0.79",
                "radius_group": "matrix_range_b",
            },
            "expected_rule": "range",
        },
    ]

    for case in cases:
        create_resp = await async_client.post(
            "/privilege-map/category", json=case["payload"], headers=headers
        )
        assert create_resp.status_code == 201

    reject_resp = await async_client.post(
        "/privilege-map/category",
        json={"username": "segment_admin_a", "radius_group": "matrix_invalid"},
        headers=headers,
    )
    assert reject_resp.status_code == 422

    list_a = await async_client.get("/privilege-map?username=segment_admin_a", headers=headers)
    assert list_a.status_code == 200
    groups_a = {row["radius_group"] for row in list_a.json()}
    assert {
        "matrix_exact_a",
        "matrix_range_a",
        "matrix_base_a",
        "matrix_fallback_a",
    }.issubset(groups_a)

    evaluated = _resolve_expected_rule(
        nas_ip="10.150.0.61",
        exact_ip="10.150.0.50",
        range_cidr="10.150.0.60/31",
        base_cidr="10.150.0.0/24",
    )
    assert evaluated == "range"


async def test_regression_multi_user_range_boundaries_and_non_owned_range_isolation(
    async_client: AsyncClient, superadmin_token: str
):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    seg_resp = await async_client.post(
        "/network-segments",
        json={"name": "Matrix Boundary Segment", "cidr": "10.151.0.0/24"},
        headers=headers,
    )
    assert seg_resp.status_code == 201
    segment_id = seg_resp.json()["id"]

    admin_range = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "segment_admin_a",
            "segment_id": segment_id,
            "target_start_ip": "10.151.0.10",
            "target_end_ip": "10.151.0.20",
            "radius_group": "matrix_admin_range",
        },
        headers=headers,
    )
    assert admin_range.status_code == 201

    reader_inverse_range = await async_client.post(
        "/privilege-map/category",
        json={
            "username": "segment_reader_b",
            "segment_id": segment_id,
            "target_start_ip": "10.151.0.21",
            "target_end_ip": "10.151.0.30",
            "radius_group": "matrix_reader_range",
        },
        headers=headers,
    )
    assert reader_inverse_range.status_code == 201

    lower_boundary = ipaddress.ip_address("10.151.0.10")
    upper_boundary = ipaddress.ip_address("10.151.0.20")
    first_outside = ipaddress.ip_address("10.151.0.21")
    admin_network = ipaddress.summarize_address_range(lower_boundary, upper_boundary)
    assert any(first_outside not in net for net in admin_network)

    list_admin = await async_client.get(
        "/privilege-map?username=segment_admin_a", headers=headers
    )
    list_reader = await async_client.get(
        "/privilege-map?username=segment_reader_b", headers=headers
    )
    assert list_admin.status_code == 200
    assert list_reader.status_code == 200

    admin_groups = {row["radius_group"] for row in list_admin.json()}
    reader_groups = {row["radius_group"] for row in list_reader.json()}
    assert "matrix_admin_range" in admin_groups
    assert "matrix_admin_range" not in reader_groups
    assert "matrix_reader_range" in reader_groups
    assert "matrix_reader_range" not in admin_groups
