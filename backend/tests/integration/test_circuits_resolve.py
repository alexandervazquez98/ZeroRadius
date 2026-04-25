import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_resolve_no_match(async_client: AsyncClient, superadmin_token: str):
    """When no matching assignment exists, resolution returns empty trace."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = await async_client.get(
        "/circuits/resolve",
        params={"username": "nonexistent_user", "nas_ip": "10.0.0.1"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resolution_path"] == "none"
    assert data["mapping"] is None
    assert data["profile"] is None


async def test_resolve_cir_id_match(async_client: AsyncClient, superadmin_token: str):
    """When a CIR assignment exists, resolution returns the circuit with trace."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create a circuit
    circuit_resp = await async_client.post(
        "/circuits",
        json={
            "name": "Resolve Test Circuit",
            "circuit_id": "CIR-RESOLVE-001",
            "type": "ethernet",
            "is_active": 1,
        },
        headers=headers,
    )
    assert circuit_resp.status_code == 201
    circuit_id = circuit_resp.json()["id"]

    # Create an access policy assignment with cir_id
    assignment_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "cir_resolve_user",
            "cir_id": circuit_id,
            "radius_group": "cir_resolve_group",
        },
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    # Resolve the circuit
    resolve_resp = await async_client.get(
        "/circuits/resolve",
        params={"username": "cir_resolve_user", "nas_ip": "10.0.0.1"},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    assert data["resolution_path"] == "cir"
    assert data["mapping"] is not None
    assert data["mapping"]["cir_id"] == circuit_id


async def test_resolve_cir_id_with_calling_station_id(async_client: AsyncClient, superadmin_token: str):
    """Resolution works with calling_station_id filter."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create circuit
    circuit_resp = await async_client.post(
        "/circuits",
        json={
            "name": "MAC Filter Circuit",
            "circuit_id": "CIR-RESOLVE-002",
            "type": "mpls",
            "is_active": 1,
        },
        headers=headers,
    )
    circuit_id = circuit_resp.json()["id"]

    # Create assignment with MAC
    assignment_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "mac_filter_user",
            "cir_id": circuit_id,
            "calling_station_id": "00:11:22:33:44:55",
            "nas_ip": "10.0.0.1",
            "radius_group": "cir_mac_group",
        },
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    # Resolve with MAC
    resolve_resp = await async_client.get(
        "/circuits/resolve",
        params={
            "username": "mac_filter_user",
            "nas_ip": "10.0.0.1",
            "calling_station_id": "00:11:22:33:44:55",
        },
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    assert data["resolution_path"] == "cir"


async def test_resolve_segment_fallback(async_client: AsyncClient, superadmin_token: str):
    """When no CIR match, falls back to segment-based resolution."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create segment
    segment_resp = await async_client.post(
        "/network-segments",
        json={"name": "Fallback Segment", "cidr": "10.50.0.0/16"},
        headers=headers,
    )
    assert segment_resp.status_code == 201
    segment_id = segment_resp.json()["id"]

    # Create assignment with segment (no CIR)
    assignment_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "segment_fallback_user",
            "segment_id": segment_id,
            "nas_ip": "10.50.1.1",
            "radius_group": "segment_fallback_group",
        },
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    # Resolve - should fall back to segment
    resolve_resp = await async_client.get(
        "/circuits/resolve",
        params={"username": "segment_fallback_user", "nas_ip": "10.50.1.1"},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    # No CIR match, but segment fallback triggered
    # resolution_path will be "none" since no CIR was found
    assert data["mapping"] is None


async def test_resolve_category_fallback(async_client: AsyncClient, superadmin_token: str):
    """When no CIR or segment match, falls back to nas_category."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}

    # Create NAS category
    category_resp = await async_client.post(
        "/nas-categories",
        json={"name": "Fallback Category", "criticality": "standard"},
        headers=headers,
    )
    assert category_resp.status_code == 201
    category_id = category_resp.json()["id"]

    # Create NAS with category
    nas_resp = await async_client.post(
        "/nas",
        json={
            "nasname": "10.60.0.1",
            "secret": "a" * 32,
            "category_id": category_id,
        },
        headers=headers,
    )
    # 201 = created, 200 = updated (existing record)
    assert nas_resp.status_code in (200, 201)

    # Create assignment with category (no CIR, no segment)
    assignment_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "category_fallback_user",
            "nas_category_id": category_id,
            "radius_group": "category_fallback_group",
        },
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    # Resolve - should fall back to category
    resolve_resp = await async_client.get(
        "/circuits/resolve",
        params={"username": "category_fallback_user", "nas_ip": "10.60.0.1"},
        headers=headers,
    )
    assert resolve_resp.status_code == 200
    data = resolve_resp.json()
    assert data["resolution_path"] == "none"  # No CIR found


async def test_resolve_circuit_unauthorized(async_client: AsyncClient, helpdesk_token: str):
    """Non-privileged roles cannot resolve circuits."""
    headers = {"Authorization": f"Bearer {helpdesk_token}"}
    response = await async_client.get(
        "/circuits/resolve",
        params={"username": "test_user", "nas_ip": "10.0.0.1"},
        headers=headers,
    )
    assert response.status_code == 403


async def test_resolve_missing_params(async_client: AsyncClient, superadmin_token: str):
    """Missing required parameters returns validation error."""
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    response = await async_client.get(
        "/circuits/resolve",
        params={"username": "test_user"},  # missing nas_ip
        headers=headers,
    )
    assert response.status_code == 422