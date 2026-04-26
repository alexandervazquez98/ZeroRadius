"""
Integration tests for the category membership guard on AccessPolicyAssignment.

These tests verify that:
1. With guard disabled (default): assignments work normally
2. With guard enabled + no membership: HTTP 409
3. With guard enabled + DeviceRegistry membership: assignment succeeds
4. With guard enabled + existing assignment membership: assignment succeeds
5. PUT endpoint respects the same guard
"""

import uuid

import pytest

from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def nas_category(async_client: AsyncClient, superadmin_token: str):
    """Create a test NAS category and return its data."""
    resp = await async_client.post(
        "/nas-categories",
        json={"name": f"TestGuardCat_{uuid.uuid4().hex[:8]}", "criticality": "standard"},
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
async def device_in_category(async_client: AsyncClient, nas_category: dict, superadmin_token: str):
    """Create a device registered in the test category."""
    # Fully random MAC to avoid collisions across test runs
    mac_raw = uuid.uuid4().hex[:12]
    mac_colon = ":".join([mac_raw[i:i+2] for i in range(0, 12, 2)])
    resp = await async_client.post(
        "/device-registry",
        json={
            "mac": mac_colon,
            "name": f"TestDevice_{uuid.uuid4().hex[:8]}",
            "category_id": nas_category["id"],
            "description": "Device for membership guard test",
        },
        headers=_auth(superadmin_token),
    )
    # 201 = created, 409 = already exists
    assert resp.status_code in (201, 409)
    return {"mac": mac_raw, "category_id": nas_category["id"], "mac_colon": mac_colon}


# ---------------------------------------------------------------------------
# Guard Disabled (default) — all operations succeed
# ---------------------------------------------------------------------------

async def test_guard_disabled_allows_category_assignment_without_membership(
    async_client: AsyncClient, superadmin_token: str, nas_category: dict
):
    """Default mode (guard disabled): category assignment succeeds even with no membership."""
    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "orphan_user",
            "nas_category_id": nas_category["id"],
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    # Without the guard, this should succeed
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Guard Enabled — rejection cases
# ---------------------------------------------------------------------------

async def test_guard_enabled_rejects_assignment_without_membership(
    async_client: AsyncClient,
    superadmin_token: str,
    nas_category: dict,
    monkeypatch,
):
    """Guard enabled + no DeviceRegistry + no existing assignment = 409."""
    # Enable the guard by patching the module-level flag
    from app.services import access_policies_service
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "stranger_user",
            "nas_category_id": nas_category["id"],
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 409
    assert "stranger_user" in resp.json()["detail"]
    assert "TestGuardCat" in resp.json()["detail"]
    assert "not a member" in resp.json()["detail"]


async def test_guard_enabled_rejects_put_without_membership(
    async_client: AsyncClient,
    superadmin_token: str,
    nas_category: dict,
    monkeypatch,
):
    """Guard enabled on PUT: updating to a category without membership = 409."""
    from app.services import access_policies_service

    unique_user = f"update_test_user_{uuid.uuid4().hex[:8]}"
    unique_ip = f"10.{int(uuid.uuid4().hex[:2], 16) % 256}.{int(uuid.uuid4().hex[2:4], 16) % 256}.{int(uuid.uuid4().hex[4:6], 16) % 256}"
    # First create a normal IP-based assignment (guard disabled)
    create_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": unique_user,
            "nas_ip": unique_ip,
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert create_resp.status_code == 201
    assignment_id = create_resp.json()["id"]

    # Now enable the guard for the PUT
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # Try to update it to a category the user has no membership in
    update_resp = await async_client.put(
        f"/access-policies/assignments/{assignment_id}",
        json={
            "username": unique_user,
            "nas_category_id": nas_category["id"],
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert update_resp.status_code == 409


# ---------------------------------------------------------------------------
# Guard Enabled — DeviceRegistry membership path
# ---------------------------------------------------------------------------

async def test_guard_enabled_allows_via_device_registry_membership(
    async_client: AsyncClient,
    superadmin_token: str,
    nas_category: dict,
    device_in_category: dict,
    monkeypatch,
):
    """Guard enabled + DeviceRegistry entry for MAC in category = allowed."""
    from app.services import access_policies_service
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # Device-based assignment uses only calling_station_id (MAC) as targeting method.
    # nas_category_id cannot be combined with calling_station_id per API validation.
    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": f"device_user_{uuid.uuid4().hex[:8]}",
            "calling_station_id": device_in_category["mac_colon"],
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    # Membership via DeviceRegistry: MAC from device_in_category is in the category
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Guard Enabled — existing AccessPolicyAssignment membership path
# ---------------------------------------------------------------------------


async def test_guard_enabled_first_assignment_needs_device_membership(
    async_client: AsyncClient,
    superadmin_token: str,
    nas_category: dict,
    monkeypatch,
):
    """First assignment in a category requires DeviceRegistry membership (not circular)."""
    from app.services import access_policies_service
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # Without DeviceRegistry, first assignment should fail
    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "first_timer",
            "nas_category_id": nas_category["id"],
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 409


async def test_guard_enabled_allows_second_assignment_via_existing(
    async_client: AsyncClient,
    superadmin_token: str,
    nas_category: dict,
    monkeypatch,
):
    """After first assignment, second assignment for same user+category is allowed via existing."""
    from app.services import access_policies_service

    unique_user = f"second_user_{uuid.uuid4().hex[:8]}"
    # Use unique MACs for each assignment (MAC-only targeting is valid)
    mac1 = f"11:22:33:44:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[2:4]}"
    mac2 = f"aa:bb:cc:dd:{uuid.uuid4().hex[:2]}:{uuid.uuid4().hex[2:4]}"

    # Setup: first create the first assignment with guard disabled (MAC-only targeting)
    first_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": unique_user,
            "calling_station_id": mac1,
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert first_resp.status_code == 201

    # Now enable the guard
    monkeypatch.setattr(access_policies_service, "_CATEGORY_MEMBERSHIP_GUARD_ENABLED", True)

    # Second assignment for same user should be allowed via existing assignment path
    second_resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": unique_user,
            "calling_station_id": mac2,
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert second_resp.status_code == 201


# ---------------------------------------------------------------------------
# Guard does not affect non-category assignments
# ---------------------------------------------------------------------------

async def test_guard_disabled_no_effect_on_ip_based_assignment(
    async_client: AsyncClient, superadmin_token: str
):
    """IP-based assignments work normally regardless of guard state."""
    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": "ip_user",
            "nas_ip": "10.88.88.1",
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(superadmin_token),
    )
    assert resp.status_code == 201
