"""
Integration tests: /nas endpoint.

Verifies:
- Any authenticated role can list NAS devices (GET /nas)
- Only superadmin/admin can create NAS (POST /nas)
- helpdesk / readonly cannot create NAS (403)
- Unauthenticated requests are rejected
"""

import pytest

# A valid NAS secret must be ≥ 32 characters (enforced by NasCreate schema)
_VALID_SECRET = "a" * 32


class TestNasRead:
    """GET /nas — list NAS devices."""

    async def test_superadmin_can_list_nas(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_admin_can_list_nas(self, async_client, admin_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert resp.status_code == 200

    async def test_helpdesk_can_list_nas(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {helpdesk_token}"}
        )
        assert resp.status_code == 200

    async def test_unauthenticated_cannot_list_nas(self, async_client):
        resp = await async_client.get("/nas")
        assert resp.status_code in (401, 403)


class TestNasCreate:
    """POST /nas — create NAS (superadmin/admin only)."""

    async def test_superadmin_can_create_nas(self, async_client, superadmin_token):
        payload = {
            "nasname": "10.99.99.1",
            "shortname": "test-nas-superadmin",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # NAS router may fail if Docker is not available (_reload_radius),
        # but the DB write succeeds — 200/201 expected
        assert resp.status_code in (200, 201)

    async def test_admin_can_create_nas(self, async_client, admin_token):
        payload = {
            "nasname": "10.99.99.2",
            "shortname": "test-nas-admin",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code in (200, 201)

    async def test_helpdesk_cannot_create_nas(self, async_client, helpdesk_token):
        payload = {
            "nasname": "10.99.99.3",
            "shortname": "test-nas-helpdesk",
            "secret": _VALID_SECRET,
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_create_nas(self, async_client, readonly_token):
        payload = {
            "nasname": "10.99.99.4",
            "shortname": "test-nas-readonly",
            "secret": _VALID_SECRET,
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_nas_secret_too_short_returns_422(self, async_client, superadmin_token):
        """NAS secret < 32 chars must be rejected by the schema validator."""
        payload = {
            "nasname": "10.99.99.5",
            "shortname": "test-nas-short-secret",
            "secret": "tooshort",
        }
        resp = await async_client.post(
            "/nas",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422


class TestNasCategoryFilter:
    """GET /nas?category_id=X — filter NAS devices by category."""

    async def test_get_nas_without_category_id_returns_all(
        self, async_client, superadmin_token, test_db
    ):
        """Without category_id param, all NAS devices are returned."""
        from app.models.models import Nas, NasCategory

        # Create two NAS with different categories
        cat1 = NasCategory(name="cat-filter-test-1", criticality="standard")
        cat2 = NasCategory(name="cat-filter-test-2", criticality="standard")
        test_db.add(cat1)
        test_db.add(cat2)
        await test_db.flush()

        nas1 = Nas(
            nasname="10.99.99.101",
            shortname="nas-cat-filter-1",
            secret=_VALID_SECRET,
            category_id=cat1.id,
        )
        nas2 = Nas(
            nasname="10.99.99.102",
            shortname="nas-cat-filter-2",
            secret=_VALID_SECRET,
            category_id=cat2.id,
        )
        test_db.add(nas1)
        test_db.add(nas2)
        await test_db.commit()

        resp = await async_client.get(
            "/nas", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 2
        nasnames = [n["nasname"] for n in data]
        assert "10.99.99.101" in nasnames
        assert "10.99.99.102" in nasnames

    async def test_get_nas_filter_by_category_id_returns_matching(
        self, async_client, superadmin_token, test_db
    ):
        """With category_id=X, only NAS with that category are returned."""
        from app.models.models import Nas, NasCategory

        cat_a = NasCategory(name="cat-a-filter-test", criticality="standard")
        cat_b = NasCategory(name="cat-b-filter-test", criticality="standard")
        test_db.add(cat_a)
        test_db.add(cat_b)
        await test_db.flush()

        nas_a = Nas(
            nasname="10.99.99.111",
            shortname="nas-cat-a",
            secret=_VALID_SECRET,
            category_id=cat_a.id,
        )
        nas_b = Nas(
            nasname="10.99.99.112",
            shortname="nas-cat-b",
            secret=_VALID_SECRET,
            category_id=cat_b.id,
        )
        test_db.add(nas_a)
        test_db.add(nas_b)
        await test_db.commit()

        resp = await async_client.get(
            f"/nas?category_id={cat_a.id}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["nasname"] == "10.99.99.111"
        assert data[0]["category_id"] == cat_a.id

    async def test_get_nas_filter_by_nonexistent_category_returns_empty(
        self, async_client, superadmin_token, test_db
    ):
        """category_id with no matching NAS returns empty list."""
        from app.models.models import Nas, NasCategory

        cat = NasCategory(name="cat-alone-filter-test", criticality="standard")
        test_db.add(cat)
        await test_db.flush()

        nas = Nas(
            nasname="10.99.99.120",
            shortname="nas-alone-cat",
            secret=_VALID_SECRET,
            category_id=cat.id,
        )
        test_db.add(nas)
        await test_db.commit()

        resp = await async_client.get(
            "/nas?category_id=99999",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_nas_filter_by_category_includes_category_name(
        self, async_client, superadmin_token, test_db
    ):
        """Filtered NAS response includes resolved category_name."""
        from app.models.models import Nas, NasCategory

        cat = NasCategory(name="cat-with-name-test", criticality="standard")
        test_db.add(cat)
        await test_db.flush()

        nas = Nas(
            nasname="10.99.99.130",
            shortname="nas-cat-name-test",
            secret=_VALID_SECRET,
            category_id=cat.id,
        )
        test_db.add(nas)
        await test_db.commit()

        resp = await async_client.get(
            f"/nas?category_id={cat.id}",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["category_name"] == "cat-with-name-test"
