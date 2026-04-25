import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_list_circuits_empty(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = await async_client.get("/circuits", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_circuit_superadmin(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload = {
        "name": "Test Circuit",
        "circuit_id": "CIR-2026-001",
        "carrier": "Verizon",
        "type": "ethernet",
        "description": "Primary backbone circuit",
        "is_active": 1,
    }
    response = await async_client.post("/circuits", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Circuit"
    assert data["circuit_id"] == "CIR-2026-001"
    assert data["carrier"] == "Verizon"
    assert data["type"] == "ethernet"
    assert data["is_active"] == 1
    assert "id" in data


async def test_create_circuit_admin(async_client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "name": "Admin Circuit",
        "circuit_id": "CIR-2026-002",
        "type": "mpls",
    }
    response = await async_client.post("/circuits", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Admin Circuit"


async def test_create_circuit_duplicate_name(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload = {
        "name": "Duplicate Name Circuit",
        "circuit_id": "CIR-2026-003",
        "type": "ethernet",
    }
    # Create first
    response1 = await async_client.post("/circuits", json=payload, headers=headers)
    assert response1.status_code == 201

    # Try duplicate name with different circuit_id
    payload2 = {**payload, "circuit_id": "CIR-2026-003-B"}
    response2 = await async_client.post("/circuits", json=payload2, headers=headers)
    assert response2.status_code == 400
    assert "name already exists" in response2.json()["detail"]


async def test_create_circuit_duplicate_circuit_id(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload1 = {
        "name": "First Circuit",
        "circuit_id": "CIR-2026-004",
        "type": "ethernet",
    }
    response1 = await async_client.post("/circuits", json=payload1, headers=headers)
    assert response1.status_code == 201

    payload2 = {
        "name": "Second Circuit",
        "circuit_id": "CIR-2026-004",
        "type": "vpn",
    }
    response2 = await async_client.post("/circuits", json=payload2, headers=headers)
    assert response2.status_code == 400
    assert "Circuit ID already exists" in response2.json()["detail"]


async def test_create_circuit_invalid_type(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    payload = {
        "name": "Invalid Type Circuit",
        "circuit_id": "CIR-2026-005",
        "type": "invalid_type",
    }
    response = await async_client.post("/circuits", json=payload, headers=headers)
    assert response.status_code == 422


async def test_create_circuit_unauthorized_roles(async_client: AsyncClient, helpdesk_token: str):
    payload = {
        "name": "Unauthorized Circuit",
        "circuit_id": "CIR-2026-006",
        "type": "ethernet",
    }
    headers = {"Authorization": f"Bearer {helpdesk_token}"}
    response = await async_client.post("/circuits", json=payload, headers=headers)
    assert response.status_code == 403


async def test_get_circuit_by_id(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create a circuit
    create_resp = await async_client.post(
        "/circuits",
        json={"name": "Get By ID Circuit", "circuit_id": "CIR-2026-007", "type": "wireless"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    circuit_id = create_resp.json()["id"]

    # Get by ID
    response = await async_client.get(f"/circuits/{circuit_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Get By ID Circuit"


async def test_get_circuit_not_found(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = await async_client.get("/circuits/99999", headers=headers)
    assert response.status_code == 404


async def test_update_circuit(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create
    create_resp = await async_client.post(
        "/circuits",
        json={"name": "Update Test Circuit", "circuit_id": "CIR-2026-008", "type": "ethernet", "is_active": 1},
        headers=headers,
    )
    assert create_resp.status_code == 201
    circuit_id = create_resp.json()["id"]

    # Update
    update_resp = await async_client.put(
        f"/circuits/{circuit_id}",
        json={"name": "Updated Circuit Name", "type": "vpn", "is_active": 0},
        headers=headers,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["name"] == "Updated Circuit Name"
    assert data["type"] == "vpn"
    assert data["is_active"] == 0


async def test_update_circuit_not_found(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = await async_client.put(
        "/circuits/99999",
        json={"name": "Nonexistent Update"},
        headers=headers,
    )
    assert response.status_code == 404


async def test_delete_circuit_superadmin(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create
    create_resp = await async_client.post(
        "/circuits",
        json={"name": "Delete Test Circuit", "circuit_id": "CIR-2026-009", "type": "ethernet"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    circuit_id = create_resp.json()["id"]

    # Delete
    delete_resp = await async_client.delete(f"/circuits/{circuit_id}", headers=headers)
    assert delete_resp.status_code == 200

    # Verify deleted
    get_resp = await async_client.get(f"/circuits/{circuit_id}", headers=headers)
    assert get_resp.status_code == 404


async def test_delete_circuit_admin_forbidden(async_client: AsyncClient, superadmin_token: str, admin_token: str):
    headers_sa = {"Authorization": f"Bearer {superadmin_token}"}
    headers_admin = {"Authorization": f"Bearer {admin_token}"}

    # Create circuit as superadmin
    create_resp = await async_client.post(
        "/circuits",
        json={"name": "Admin Delete Test", "circuit_id": "CIR-2026-010", "type": "ethernet"},
        headers=headers_sa,
    )
    assert create_resp.status_code == 201
    circuit_id = create_resp.json()["id"]

    # Admin cannot delete
    delete_resp = await async_client.delete(f"/circuits/{circuit_id}", headers=headers_admin)
    assert delete_resp.status_code == 403

    # Cleanup as superadmin
    await async_client.delete(f"/circuits/{circuit_id}", headers=headers_sa)


async def test_delete_circuit_with_active_assignments(async_client: AsyncClient, superadmin_token: str):
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create circuit
    create_resp = await async_client.post(
        "/circuits",
        json={"name": "Circuit With Assignment", "circuit_id": "CIR-2026-011", "type": "ethernet"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    circuit_id = create_resp.json()["id"]

    # Create assignment using the circuit
    assignment_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "cir_test_user",
            "cir_id": circuit_id,
            "radius_group": "cir_group_1",
        },
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    # Try to delete circuit - should fail
    delete_resp = await async_client.delete(f"/circuits/{circuit_id}", headers=headers)
    assert delete_resp.status_code == 409
    assert "dependent access policy assignments exist" in delete_resp.json()["detail"]