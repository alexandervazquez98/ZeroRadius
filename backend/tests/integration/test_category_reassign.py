"""Integration tests for category reassignment endpoint."""
import pytest


@pytest.mark.asyncio
async def test_reassign_category_success(async_client, db_session, superadmin_token):
    """Successful reassignment returns updated count."""
    # Create two categories
    cat1_resp = await async_client.post(
        "/nas-categories",
        json={"name": "source-cat", "criticality": "standard"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert cat1_resp.status_code == 201
    cat1_id = cat1_resp.json()["id"]

    cat2_resp = await async_client.post(
        "/nas-categories",
        json={"name": "target-cat", "criticality": "standard"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert cat2_resp.status_code == 201
    cat2_id = cat2_resp.json()["id"]

    # Create assignments under cat1
    for i in range(3):
        await async_client.post(
            "/access-policies/assignments",
            json={
                "username": f"user{i}",
                "nas_category_id": cat1_id,
                "radius_group": "test-group",
            },
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )

    # Reassign all from cat1 to cat2
    resp = await async_client.patch(
        f"/access-policies/categories/{cat1_id}/reassign",
        json={"target_category_id": cat2_id},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3


@pytest.mark.asyncio
async def test_reassign_category_target_not_found(async_client, superadmin_token):
    """Returns 404 when target category does not exist."""
    # Create source category but use non-existent target
    cat_resp = await async_client.post(
        "/nas-categories",
        json={"name": "only-cat", "criticality": "standard"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert cat_resp.status_code == 201
    cat_id = cat_resp.json()["id"]

    resp = await async_client.patch(
        f"/access-policies/categories/{cat_id}/reassign",
        json={"target_category_id": 99999},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 404
    assert "Target category not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reassign_category_no_assignments(async_client, superadmin_token):
    """Returns 0 when source category has no assignments."""
    # Create two categories with no assignments
    cat1_resp = await async_client.post(
        "/nas-categories",
        json={"name": "empty1", "criticality": "standard"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert cat1_resp.status_code == 201
    cat1_id = cat1_resp.json()["id"]

    cat2_resp = await async_client.post(
        "/nas-categories",
        json={"name": "empty2", "criticality": "standard"},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert cat2_resp.status_code == 201
    cat2_id = cat2_resp.json()["id"]

    resp = await async_client.patch(
        f"/access-policies/categories/{cat1_id}/reassign",
        json={"target_category_id": cat2_id},
        headers={"Authorization": f"Bearer {superadmin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 0


@pytest.mark.asyncio
async def test_reassign_category_unauthorized(async_client, auditor_token):
    """Returns 403 for unauthorized role (Auditor)."""
    resp = await async_client.patch(
        "/access-policies/categories/1/reassign",
        json={"target_category_id": 2},
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reassign_category_admin_allowed(async_client, admin_token):
    """Admin role is allowed (not just SUPERADMIN)."""
    # Create two categories
    cat1_resp = await async_client.post(
        "/nas-categories",
        json={"name": "admin-test1", "criticality": "standard"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cat1_resp.status_code == 201
    cat1_id = cat1_resp.json()["id"]

    cat2_resp = await async_client.post(
        "/nas-categories",
        json={"name": "admin-test2", "criticality": "standard"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert cat2_resp.status_code == 201
    cat2_id = cat2_resp.json()["id"]

    # Admin can call the endpoint (even if no assignments to reassign)
    resp = await async_client.patch(
        f"/access-policies/categories/{cat1_id}/reassign",
        json={"target_category_id": cat2_id},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200