"""
Integration tests: /dictionary endpoint.

Verifies:
- Any authenticated role can list dictionary files (GET /dictionary/files)
- Any authenticated role can query attributes (GET /dictionary/attributes)
- GET /dictionary/attributes gracefully handles Docker unavailability
- GET /dictionary/builtin returns a list of built-in vendor dictionaries
- GET /dictionary/builtin/{filename} returns file content
- Path traversal is rejected on /dictionary/builtin/{filename}
- Unauthenticated requests are rejected
"""

import pytest
from unittest.mock import patch


class TestDictionaryRead:
    """GET /dictionary/files and /dictionary/attributes — authenticated access."""

    async def test_superadmin_can_list_dictionary_files(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_list_dictionary_files(self, async_client, admin_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_list_dictionary_files(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_readonly_can_list_dictionary_files(self, async_client, readonly_token):
        resp = await async_client.get(
            "/dictionary/files",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200

    async def test_superadmin_can_list_attributes(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/dictionary/attributes",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_unauthenticated_cannot_list_dictionary_files(self, async_client):
        resp = await async_client.get("/dictionary/files")
        assert resp.status_code in (401, 403)

    async def test_unauthenticated_cannot_list_attributes(self, async_client):
        resp = await async_client.get("/dictionary/attributes")
        assert resp.status_code in (401, 403)


class TestAttributesMerge:
    """GET /dictionary/attributes — merges custom + built-in dicts."""

    async def test_attributes_returns_200_when_docker_unavailable(
        self, async_client, superadmin_token
    ):
        """When Docker / radius-server is not reachable, endpoint must still
        return 200 with the custom dict attributes (graceful degradation)."""
        import app.routers.dictionary as dict_router
        dict_router._builtin_attr_cache = None

        with patch(
            "app.routers.dictionary._exec_in_radius",
            side_effect=RuntimeError("Docker not available"),
        ):
            resp = await async_client.get(
                "/dictionary/attributes",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_attributes_includes_builtin_when_docker_available(
        self, async_client, superadmin_token
    ):
        """When Docker returns valid grep output, built-in attrs appear in the list."""
        mock_grep = (
            "/usr/share/freeradius/dictionary.cisco:BEGIN-VENDOR\tCisco\n"
            "/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-AVPair\t1\tstring\n"
            "/usr/share/freeradius/dictionary.cisco:END-VENDOR\tCisco\n"
        )
        import app.routers.dictionary as dict_router
        dict_router._builtin_attr_cache = None

        with patch(
            "app.routers.dictionary._exec_in_radius",
            return_value=mock_grep,
        ):
            resp = await async_client.get(
                "/dictionary/attributes",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        names = [a["name"] for a in data]
        assert "Cisco-AVPair" in names

    async def test_builtin_attrs_tagged_with_sistema_prefix(
        self, async_client, superadmin_token
    ):
        """Built-in attribute dictionary field must start with '[Sistema]'."""
        mock_grep = (
            "/usr/share/freeradius/dictionary.cisco:BEGIN-VENDOR\tCisco\n"
            "/usr/share/freeradius/dictionary.cisco:ATTRIBUTE\tCisco-AVPair\t1\tstring\n"
            "/usr/share/freeradius/dictionary.cisco:END-VENDOR\tCisco\n"
        )
        import app.routers.dictionary as dict_router
        dict_router._builtin_attr_cache = None

        with patch(
            "app.routers.dictionary._exec_in_radius",
            return_value=mock_grep,
        ):
            resp = await async_client.get(
                "/dictionary/attributes",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )

        data = resp.json()
        cisco_attr = next((a for a in data if a["name"] == "Cisco-AVPair"), None)
        assert cisco_attr is not None
        assert cisco_attr["dictionary"].startswith("[Sistema]")
        assert cisco_attr["vendor"] == "Cisco"


class TestBuiltinDictionaryEndpoint:
    """GET /dictionary/builtin and GET /dictionary/builtin/{filename}."""

    async def test_list_builtin_requires_auth(self, async_client):
        resp = await async_client.get("/dictionary/builtin")
        assert resp.status_code in (401, 403)

    async def test_list_builtin_returns_list_when_docker_available(
        self, async_client, superadmin_token
    ):
        mock_ls = "dictionary.cisco\ndictionary.microsoft\n"
        with patch(
            "app.routers.dictionary._exec_in_radius",
            return_value=mock_ls,
        ):
            resp = await async_client.get(
                "/dictionary/builtin",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        vendors = [d["vendor"] for d in data]
        assert "cisco" in vendors
        assert "microsoft" in vendors

    async def test_list_builtin_returns_503_when_docker_unavailable(
        self, async_client, superadmin_token
    ):
        with patch(
            "app.routers.dictionary._exec_in_radius",
            side_effect=RuntimeError("Docker not available"),
        ):
            resp = await async_client.get(
                "/dictionary/builtin",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )
        assert resp.status_code == 503

    async def test_get_builtin_content_requires_auth(self, async_client):
        resp = await async_client.get("/dictionary/builtin/dictionary.cisco")
        assert resp.status_code in (401, 403)

    async def test_get_builtin_content_returns_text(
        self, async_client, superadmin_token
    ):
        mock_content = "VENDOR\tCisco\t9\nATTRIBUTE\tCisco-AVPair\t1\tstring\n"
        with patch(
            "app.routers.dictionary._exec_in_radius",
            return_value=mock_content,
        ):
            resp = await async_client.get(
                "/dictionary/builtin/dictionary.cisco",
                headers={"Authorization": f"Bearer {superadmin_token}"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["filename"] == "dictionary.cisco"
        assert "Cisco-AVPair" in data["content"]
        assert data["builtin"] is True

    async def test_regression_path_traversal_blocked(
        self, async_client, superadmin_token
    ):
        """GET /dictionary/builtin/../../../etc/passwd must return 400.

        Regression for potential path traversal via filename parameter.
        """
        resp = await async_client.get(
            "/dictionary/builtin/../../../etc/passwd",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # FastAPI URL decoding may change the path, but our regex validation
        # should catch any non-matching filename pattern.
        assert resp.status_code in (400, 404, 422)

    async def test_regression_filename_without_dictionary_prefix_blocked(
        self, async_client, superadmin_token
    ):
        """Only filenames matching 'dictionary.*' pattern are allowed.

        Regression: arbitrary filenames like 'shadow' must be rejected.
        """
        resp = await async_client.get(
            "/dictionary/builtin/shadow",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 400
