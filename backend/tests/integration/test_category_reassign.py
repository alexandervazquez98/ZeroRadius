import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_nas_category(async_client: AsyncClient, token: str, name: str) -> int:
    resp = await async_client.post(
        "/nas-categories",
        json={"name": name, "criticality": "standard"},
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_assignment(
    async_client: AsyncClient, token: str, nas_category_id: int, username: str
) -> int:
    resp = await async_client.post(
        "/access-policies/assignments",
        json={
            "username": username,
            "nas_category_id": nas_category_id,
            "radius_group": "test_group",
            "approved_by": "test_superadmin",
            "is_active": 1,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_reassign_category_success(
    async_client: AsyncClient, superadmin_token: str
):
    """Test bulk reassignment of access policies from one category to another."""
    cat_a = await _create_nas_category(async_client, superadmin_token, "CategoryA")
    cat_b = await _create_nas_category(async_client, superadmin_token, "CategoryB")

    # Create assignments under cat_a
    id1 = await _create_assignment(async_client, superadmin_token, cat_a, "user1")
    id2 = await _create_assignment(async_client, superadmin_token, cat_a, "user2")
    id3 = await _create_assignment(async_client, superadmin_token, cat_a, "user3")

    # Verify assignments are under cat_a
    list_resp = await async_client.get(
        f"/access-policies/assignments?nas_category_id={cat_a}",
        headers=_auth(superadmin_token),
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 3

    # Reassign all from cat_a to cat_b
    reassign_resp = await async_client.patch(
        f"/access-policies/categories/{cat_a}/reassign",
        json={"target_category_id": cat_b},
        headers=_auth(superadmin_token),
    )
    assert reassign_resp.status_code == 200
    assert reassign_resp.json()["updated"] == 3

    # Verify cat_a is now empty
    empty_resp = await async_client.get(
        f"/access-policies/assignments?nas_category_id={cat_a}",
        headers=_auth(superadmin_token),
    )
    assert empty_resp.status_code == 200
    assert len(empty_resp.json()) == 0

    # Verify all assignments are now under cat_b
    list_b = await async_client.get(
        f"/access-policies/assignments?nas_category_id={cat_b}",
        headers=_auth(superadmin_token),
    )
    assert list_b.status_code == 200
    assert len(list_b.json()) == 3


async def test_reassign_category_target_not_found(
    async_client: AsyncClient, superadmin_token: str
):
    """Test that reassignment fails when target category does not exist."""
    cat_a = await _create_nas_category(async_client, superadmin_token, "CategoryA")
    await _create_assignment(async_client, superadmin_token, cat_a, "orphan_user")

    reassign_resp = await async_client.patch(
        f"/access-policies/categories/{cat_a}/reassign",
        json={"target_category_id": 99999},
        headers=_auth(superadmin_token),
    )
    assert reassign_resp.status_code == 404
    assert reassign_resp.json()["detail"] == "Target category not found"


async def test_reassign_category_empty_source(
    async_client: AsyncClient, superadmin_token: str
):
    """Test reassignment when source category has no assignments."""
    cat_a = await _create_nas_category(async_client, superadmin_token, "CategoryA")
    cat_b = await _create_nas_category(async_client, superadmin_token, "CategoryB")

    reassign_resp = await async_client.patch(
        f"/access-policies/categories/{cat_a}/reassign",
        json={"target_category_id": cat_b},
        headers=_auth(superadmin_token),
    )
    assert reassign_resp.status_code == 200
    assert reassign_resp.json()["updated"] == 0


async def test_reassign_category_unauthorized_roles(
    async_client: AsyncClient,
    superadmin_token: str,
    helpdesk_token: str,
    auditor_token: str,
    readonly_token: str,
):
    """Test that non-admin roles cannot reassign categories."""
    cat_a = await _create_nas_category(async_client, superadmin_token, "CategoryA")
    cat_b = await _create_nas_category(async_client, superadmin_token, "CategoryB")

    for token in [helpdesk_token, auditor_token, readonly_token]:
        resp = await async_client.patch(
            f"/access-policies/categories/{cat_a}/reassign",
            json={"target_category_id": cat_b},
            headers=_auth(token),
        )
        assert resp.status_code == 403


async def test_reassign_category_admin_allowed(
    async_client: AsyncClient, superadmin_token: str, admin_token: str
):
    """Test that admin role can reassign categories."""
    cat_a = await _create_nas_category(async_client, superadmin_token, "CategoryA")
    cat_b = await _create_nas_category(async_client, superadmin_token, "CategoryB")

    await _create_assignment(async_client, superadmin_token, cat_a, "admin_test_user")

    resp = await async_client.patch(
        f"/access-policies/categories/{cat_a}/reassign",
        json={"target_category_id": cat_b},
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["updated"] == 1
