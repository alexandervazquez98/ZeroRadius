import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


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
    response = await async_client.post(
        "/privilege-map", json=payload, headers=headers
    )
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
