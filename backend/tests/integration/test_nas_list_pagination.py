"""
Integration tests: GET /nas pagination and filters (issue #127).

- limit/offset paginate; X-Total-Count is the filtered total before paging
- nasname/shortname/type/description: case-insensitive partial match
- filters combine (AND); secret is never a filter
- without limit the full list is returned exactly as before

The test database is shared across the session and rows are committed, so
every test seeds rows whose shortname starts with a unique tag and scopes its
queries with ``shortname=<tag>``.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio

_SECRET = "a" * 32
_SECRET_MARKER = "zzsecretmarker"


@pytest.fixture
def tag():
    return "pg" + uuid.uuid4().hex[:6]


async def _seed(test_db, tag):
    from app.models.models import Nas, NasCategory

    core = NasCategory(name=f"{tag}-core", criticality="critical")
    edge = NasCategory(name=f"{tag}-edge", criticality="standard")
    test_db.add_all([core, edge])
    await test_db.flush()
    rows = [
        Nas(nasname="10.10.0.1", shortname=f"{tag}-Core-SW-01", type="cisco",
            secret=_SECRET_MARKER + "x" * 20, description="Main Building core",
            category_id=core.id),
        Nas(nasname="10.10.0.2", shortname=f"{tag}-core-sw-02", type="cisco",
            secret=_SECRET, description="Backup core", category_id=core.id),
        Nas(nasname="10.20.0.0/24", shortname=f"{tag}-ap-lobby", type="ubiquiti",
            secret=_SECRET, description="Lobby access points", category_id=edge.id),
        Nas(nasname="192.168.5.10", shortname=f"{tag}-edge-fw", type="other",
            secret=_SECRET, description="Perimeter firewall", category_id=edge.id),
        Nas(nasname="172.16.0.9", shortname=f"{tag}-lab-ap", type="ubiquiti",
            secret=_SECRET, description=None, category_id=None),
    ]
    test_db.add_all(rows)
    await test_db.commit()
    return core, edge


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _names(resp, tag):
    """Shortnames without the tag prefix."""
    return [n["shortname"].removeprefix(f"{tag}-") for n in resp.json()]


class TestNasPagination:
    async def test_limit_offset_paginate_with_total_count(
        self, async_client, superadmin_token, test_db, tag
    ):
        await _seed(test_db, tag)
        pages = [
            await async_client.get(
                f"/nas?shortname={tag}&limit=2&offset={offset}",
                headers=_auth(superadmin_token),
            )
            for offset in (0, 2, 4)
        ]
        assert [p.status_code for p in pages] == [200, 200, 200]
        assert _names(pages[0], tag) == ["Core-SW-01", "core-sw-02"]
        assert _names(pages[1], tag) == ["ap-lobby", "edge-fw"]
        assert _names(pages[2], tag) == ["lab-ap"]
        for resp in pages:
            assert resp.headers["X-Total-Count"] == "5"

    async def test_without_limit_returns_full_list_as_before(
        self, async_client, superadmin_token, test_db, tag
    ):
        await _seed(test_db, tag)
        resp = await async_client.get("/nas", headers=_auth(superadmin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Full table, ordered by id, every row serialized with the same fields
        assert [n["id"] for n in data] == sorted(n["id"] for n in data)
        assert resp.headers["X-Total-Count"] == str(len(data))
        ours = [n for n in data if (n["shortname"] or "").startswith(tag)]
        assert [n["shortname"].removeprefix(f"{tag}-") for n in ours] == [
            "Core-SW-01", "core-sw-02", "ap-lobby", "edge-fw", "lab-ap",
        ]
        assert set(ours[0]) == {
            "id", "nasname", "shortname", "type", "ports", "secret",
            "description", "category_id", "category_name",
        }
        assert ours[0]["category_name"] == f"{tag}-core"

    @pytest.mark.parametrize(
        "query",
        ["limit=0", "limit=101", "limit=abc", "offset=-1", "limit=10&offset=-5"],
    )
    async def test_invalid_limit_or_offset_returns_422(
        self, async_client, superadmin_token, query
    ):
        resp = await async_client.get(f"/nas?{query}", headers=_auth(superadmin_token))
        assert resp.status_code == 422

    async def test_category_id_non_positive_still_422(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/nas?category_id=0&limit=10", headers=_auth(superadmin_token)
        )
        assert resp.status_code == 422


class TestNasFilters:
    async def _get(self, client, token, tag, query):
        return await client.get(f"/nas?shortname={tag}&{query}", headers=_auth(token))

    async def test_filter_nasname_partial(self, async_client, superadmin_token, test_db, tag):
        await _seed(test_db, tag)
        resp = await self._get(async_client, superadmin_token, tag, "nasname=10.10.")
        assert _names(resp, tag) == ["Core-SW-01", "core-sw-02"]
        cidr = await self._get(async_client, superadmin_token, tag, "nasname=0/24")
        assert _names(cidr, tag) == ["ap-lobby"]

    async def test_filter_shortname_case_insensitive(
        self, async_client, superadmin_token, test_db, tag
    ):
        await _seed(test_db, tag)
        resp = await async_client.get(
            f"/nas?shortname={tag.upper()}-CORE-sw", headers=_auth(superadmin_token)
        )
        assert _names(resp, tag) == ["Core-SW-01", "core-sw-02"]

    async def test_filter_type_partial(self, async_client, superadmin_token, test_db, tag):
        await _seed(test_db, tag)
        resp = await self._get(async_client, superadmin_token, tag, "type=UBIQ")
        assert _names(resp, tag) == ["ap-lobby", "lab-ap"]

    async def test_filter_description_case_insensitive(
        self, async_client, superadmin_token, test_db, tag
    ):
        await _seed(test_db, tag)
        resp = await self._get(async_client, superadmin_token, tag, "description=CORE")
        assert _names(resp, tag) == ["Core-SW-01", "core-sw-02"]

    async def test_filter_category_id(self, async_client, superadmin_token, test_db, tag):
        _, edge = await _seed(test_db, tag)
        resp = await async_client.get(
            f"/nas?category_id={edge.id}", headers=_auth(superadmin_token)
        )
        assert _names(resp, tag) == ["ap-lobby", "edge-fw"]
        assert resp.headers["X-Total-Count"] == "2"

    async def test_filters_combine_with_and(self, async_client, superadmin_token, test_db, tag):
        core, _ = await _seed(test_db, tag)
        resp = await async_client.get(
            f"/nas?category_id={core.id}&shortname=sw&description=backup",
            headers=_auth(superadmin_token),
        )
        assert _names(resp, tag) == ["core-sw-02"]
        assert resp.headers["X-Total-Count"] == "1"

    async def test_filters_with_pagination_total_is_filtered_total(
        self, async_client, superadmin_token, test_db, tag
    ):
        await _seed(test_db, tag)
        resp = await self._get(
            async_client, superadmin_token, tag, "type=ubiquiti&limit=1&offset=1"
        )
        assert _names(resp, tag) == ["lab-ap"]
        assert resp.headers["X-Total-Count"] == "2"

    async def test_secret_is_not_a_filter(self, async_client, superadmin_token, test_db, tag):
        await _seed(test_db, tag)
        resp = await self._get(async_client, superadmin_token, tag, f"secret={_SECRET_MARKER}")
        assert resp.status_code == 200
        assert len(resp.json()) == 5
        assert resp.headers["X-Total-Count"] == "5"
        # Text filters never match on the secret column either
        for field in ("nasname", "shortname", "type", "description"):
            hit = await async_client.get(
                f"/nas?{field}={_SECRET_MARKER}", headers=_auth(superadmin_token)
            )
            assert hit.json() == [], field
            assert hit.headers["X-Total-Count"] == "0"
