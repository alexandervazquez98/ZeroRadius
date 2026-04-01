"""
Integration tests: /iam-nac endpoints (RBAC, Macros, Policy Compiler Engine, JIT).

Verifies:
- Creation of Policy Macros
- Compiler Engine validation with pyrad dictionaries
- Regression: compile with built-in attrs when pyrad dict is empty
- JIT Access Elevation flow inserting the Expiration attribute
"""

import pytest

pytestmark = pytest.mark.asyncio

from unittest.mock import patch


class TestIAMNAC:
    """Tests for Policy Macros and Compiler Engine."""

    @patch("app.routers.iam_nac.dictionary_service")
    async def test_create_macro_and_compile_success(self, mock_dict_service, async_client, superadmin_token):
        """Compile a macro with custom dict attrs — normal path."""
        class MockDict:
            attributes = {"Framed-MTU": True, "Reply-Message": True}

        mock_dict_service.dictionary = MockDict()

        payload = {
            "name": "Integration-Macro-1",
            "description": "Test Macro",
            "attributes_json": {
                "attributes": [
                    {"name": "Framed-MTU", "op": "=", "value": "1500"},
                    {"name": "Reply-Message", "op": "=", "value": "Welcome"},
                ]
            },
        }
        resp = await async_client.post(
            "/iam-nac/macros",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        macro_id = resp.json()["id"]

        compile_resp = await async_client.post(
            f"/iam-nac/compile/{macro_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert compile_resp.status_code == 200
        data = compile_resp.json()
        assert data["attributes_compiled"] == 2
        # Group name is the safe policy name (spaces→underscores), NOT "POL_{id}_{name}"
        assert data["compiled_group_name"] == "Integration-Macro-1"

    @patch("app.routers.iam_nac.dictionary_service")
    async def test_compile_fails_invalid_attribute(self, mock_dict_service, async_client, superadmin_token):
        """Compile a macro with an attribute not in any dictionary — must return 400."""
        class MockDict:
            attributes = {"Framed-MTU": True, "Reply-Message": True}

        mock_dict_service.dictionary = MockDict()

        payload = {
            "name": "Integration-Macro-Fail",
            "description": "Test Macro Fail",
            "attributes_json": {
                "attributes": [
                    {"name": "Cisco-Invalid-Trait-XZY-9999", "op": "=", "value": "1500"}
                ]
            },
        }
        resp = await async_client.post(
            "/iam-nac/macros",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        macro_id = resp.json()["id"]

        compile_resp = await async_client.post(
            f"/iam-nac/compile/{macro_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert compile_resp.status_code == 400
        # Error message references the unified (custom | builtin) validation
        assert "not found in any loaded RADIUS dictionary" in compile_resp.json()["detail"]

    @patch("app.routers.iam_nac._get_builtin_attributes_cached")
    @patch("app.routers.iam_nac.dictionary_service")
    async def test_regression_compile_builtin_attr_with_empty_pyrad(
        self, mock_dict_service, mock_builtin_cache, async_client, superadmin_token
    ):
        """
        Regression test for bug fixed 2026-04-01.

        Root cause: pyrad.Dictionary() initializes completely empty (0 attrs).
        When compile validated ONLY against pyrad dict, built-in vendor attrs like
        Cisco-AVPair always failed with 400 — even though they ARE valid in FreeRADIUS.

        Fix: validate against custom_attrs | builtin_attrs (iam_nac.py:143).

        This test simulates the exact failure scenario:
          - pyrad dict is empty (no custom dictionaries loaded)
          - builtin cache has Cisco-AVPair
          - compile MUST succeed and write 1 row to radgroupreply
        """
        # Simulate pyrad dict empty (as it initializes by default with no files)
        class EmptyPyradDict:
            attributes = {}

        mock_dict_service.dictionary = EmptyPyradDict()

        # Simulate builtin cache returning Cisco-AVPair from radius-server container
        mock_builtin_cache.return_value = [
            {
                "name": "Cisco-AVPair",
                "type": "string",
                "source": "dictionary.cisco",
                "source_type": "builtin",
            }
        ]

        payload = {
            "name": "Regression-Cisco-Builtin",
            "description": "Regression: builtin attr must compile when pyrad dict is empty",
            "attributes_json": {
                "attributes": [
                    {"name": "Cisco-AVPair", "op": ":=", "value": "shell:priv-lvl=15"}
                ]
            },
        }
        resp = await async_client.post(
            "/iam-nac/macros",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        macro_id = resp.json()["id"]

        # Must succeed — Cisco-AVPair comes from builtin cache, not pyrad
        compile_resp = await async_client.post(
            f"/iam-nac/compile/{macro_id}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert compile_resp.status_code == 200, (
            f"Regression: compile failed with empty pyrad + builtin Cisco-AVPair: "
            f"{compile_resp.json()}"
        )
        data = compile_resp.json()
        assert data["attributes_compiled"] == 1
        assert data["compiled_group_name"] == "Regression-Cisco-Builtin"


class TestJITWorkflow:
    """Tests for the Break-Glass JIT module."""

    async def test_jit_approve_injects_expiration(self, async_client, superadmin_token):
        username = "jit_test_user_001"
        ttl_hours = 24

        resp = await async_client.post(
            f"/iam-nac/jit-requests/{username}/approve?ttl_hours={ttl_hours}",
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
