"""
Integration tests: /users/jit-requests endpoints (Break-Glass JIT).

Verifies:
- JIT Access Elevation flow inserting the Expiration attribute
"""

import pytest

pytestmark = pytest.mark.asyncio


class TestJITWorkflow:
    """Tests for the Break-Glass JIT module."""

    async def test_jit_approve_injects_expiration(self, async_client, superadmin_token):
        username = "jit_test_user_001"
        ttl_hours = 24

        resp = await async_client.post(
            f"/users/jit-requests/{username}/approve?ttl_hours={ttl_hours}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200

        list_resp = await async_client.get(
            "/users",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert list_resp.status_code == 200
        user_checks = [c for c in list_resp.json() if c["username"] == username]
        expiration_check = next(
            (c for c in user_checks if c["attribute"] == "Expiration"), None
        )
        assert expiration_check is not None
        assert expiration_check["op"] == ":="
        assert isinstance(expiration_check["value"], str)
