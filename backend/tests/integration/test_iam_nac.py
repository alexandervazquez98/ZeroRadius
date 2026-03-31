"""
Integration tests: /iam-nac endpoints (RBAC, Macros, Policy Compiler Engine, JIT).

Verifies:
- Creation of Policy Macros
- Compiler Engine validation with pyrad dictionaries
- JIT Access Elevation flow inserting the Expiration attribute
"""

import pytest

pytestmark = pytest.mark.asyncio

from unittest.mock import patch

class TestIAMNAC:
    """Tests for Policy Macros and Compiler Engine."""

    @patch("app.routers.iam_nac.dictionary_service")
    async def test_create_macro_and_compile_success(self, mock_dict_service, async_client, superadmin_token):
        # Mock dictionary to treat our attributes as valid
        class MockDict:
            attributes = True
            def __contains__(self, item):
                return item in ["Framed-MTU", "Reply-Message"]
        
        mock_dict_service.dictionary = MockDict()

        # 1. Create a macro with valid attributes
        payload = {
            "name": "Integration-Macro-1",
            "description": "Test Macro",
            "attributes_json": {
                "attributes": [
                    {"name": "Framed-MTU", "op": "=", "value": "1500"},
                    {"name": "Reply-Message", "op": "=", "value": "Welcome"}
                ]
            }
        }
        resp = await async_client.post(
            "/iam-nac/macros",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        macro_id = resp.json()["id"]

        # 2. Compile macro
        compile_resp = await async_client.post(
            f"/iam-nac/compile/{macro_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert compile_resp.status_code == 200
        data = compile_resp.json()
        assert data["attributes_compiled"] == 2
        assert data["compiled_group_name"].startswith(f"POL_{macro_id}_")

    @patch("app.routers.iam_nac.dictionary_service")
    async def test_compile_fails_invalid_attribute(self, mock_dict_service, async_client, superadmin_token):
        # Mock dictionary to treat our attributes as valid
        class MockDict:
            attributes = True
            def __contains__(self, item):
                return item in ["Framed-MTU", "Reply-Message"]
        
        mock_dict_service.dictionary = MockDict()

        # 1. Create a macro with an invalid attribute name
        payload = {
            "name": "Integration-Macro-Fail",
            "description": "Test Macro Fail",
            "attributes_json": {
                "attributes": [
                    {"name": "Cisco-Invalid-Trait-XZY", "op": "=", "value": "1500"}
                ]
            }
        }
        resp = await async_client.post(
            "/iam-nac/macros",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        macro_id = resp.json()["id"]

        # 2. Compile macro -> should return 400 because attribute isn't in dictionary
        compile_resp = await async_client.post(
            f"/iam-nac/compile/{macro_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert compile_resp.status_code == 400
        assert "not found in FreeRADIUS dictionary" in compile_resp.json()["detail"]


class TestJITWorkflow:
    """Tests for the Break-Glass JIT module."""

    async def test_jit_approve_injects_expiration(self, async_client, superadmin_token):
        username = "jit_test_user_001"
        ttl_hours = 24

        # Approve JIT flow
        resp = await async_client.post(
            f"/iam-nac/jit-requests/{username}/approve?ttl_hours={ttl_hours}",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        
        # Verify it created an "Expiration" attribute in the system
        list_resp = await async_client.get(
            "/users",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert list_resp.status_code == 200
        user_checks = [c for c in list_resp.json() if c["username"] == username]
        expiration_check = next((c for c in user_checks if c["attribute"] == "Expiration"), None)
        assert expiration_check is not None
        assert expiration_check["op"] == ":="
        assert isinstance(expiration_check["value"], str)
