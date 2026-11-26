"""
Integration tests: GET /syslog list (#136).

The list is limited to a time window (default the last 8 h, at most 8 h) and
paginates with a keyset cursor instead of OFFSET + an exact COUNT(*), which
scanned the whole table on every page. The session-scoped test DB is shared
with other tests, so every query filters on this module's 203.0.113.0/24 IPs.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.models import SyslogEvent

_NET = "203.0.113."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


async def _add(db, device_ip, received_at, message="list probe", severity=6):
    # Explicit id: SQLite does not autoincrement the BIGINT primary key.
    next_id = (await db.execute(select(func.coalesce(func.max(SyslogEvent.id), 0)))).scalar() + 1
    db.add(
        SyslogEvent(
            id=next_id,
            received_at=received_at,
            device_ip=device_ip,
            facility=16,
            severity=severity,
            program="test",
            message=message,
        )
    )
    await db.commit()
    return next_id


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _get(client, token, **params):
    return await client.get("/syslog", params=params, headers=_auth(token))


class TestTimeWindow:
    async def test_default_window_is_last_8_hours(self, async_client, superadmin_token, test_db):
        now = _now()
        await _add(test_db, _NET + "1", now - timedelta(hours=1), "recent")
        await _add(test_db, _NET + "1", now - timedelta(hours=9), "too old")

        resp = await _get(async_client, superadmin_token, device_ip=_NET + "1")
        assert resp.status_code == 200
        body = resp.json()
        assert [e["message"] for e in body["events"]] == ["recent"]
        assert body["max_range_hours"] == 8
        start = datetime.fromisoformat(body["start_date"])
        end = datetime.fromisoformat(body["end_date"])
        assert end - start == timedelta(hours=8)

    async def test_window_longer_than_8_hours_is_rejected(self, async_client, superadmin_token):
        now = _now()
        resp = await _get(
            async_client, superadmin_token,
            start_date=_iso(now - timedelta(hours=9)), end_date=_iso(now),
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "The time range cannot exceed 8 hours."

    async def test_end_before_start_is_rejected(self, async_client, superadmin_token):
        now = _now()
        resp = await _get(
            async_client, superadmin_token,
            start_date=_iso(now), end_date=_iso(now - timedelta(hours=1)),
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "end_date must be after start_date."

    async def test_start_only_covers_the_next_8_hours(self, async_client, superadmin_token, test_db):
        base = _now() - timedelta(days=3)
        await _add(test_db, _NET + "2", base + timedelta(hours=7), "inside")
        await _add(test_db, _NET + "2", base + timedelta(hours=9), "outside")

        resp = await _get(async_client, superadmin_token, device_ip=_NET + "2", start_date=_iso(base))
        body = resp.json()
        assert [e["message"] for e in body["events"]] == ["inside"]
        assert datetime.fromisoformat(body["end_date"]) == base + timedelta(hours=8)

    async def test_end_only_covers_the_previous_8_hours(self, async_client, superadmin_token, test_db):
        end = _now() - timedelta(days=4)
        await _add(test_db, _NET + "3", end - timedelta(hours=7), "inside")
        await _add(test_db, _NET + "3", end - timedelta(hours=9), "outside")

        resp = await _get(async_client, superadmin_token, device_ip=_NET + "3", end_date=_iso(end))
        assert [e["message"] for e in resp.json()["events"]] == ["inside"]

    async def test_old_8_hour_window_is_allowed(self, async_client, superadmin_token, test_db):
        start = _now() - timedelta(days=30)
        await _add(test_db, _NET + "4", start + timedelta(hours=1), "last month")

        resp = await _get(
            async_client, superadmin_token, device_ip=_NET + "4",
            start_date=_iso(start), end_date=_iso(start + timedelta(hours=8)),
        )
        assert resp.status_code == 200
        assert [e["message"] for e in resp.json()["events"]] == ["last month"]


class TestKeysetPagination:
    async def test_pages_follow_the_cursor_without_gaps(self, async_client, superadmin_token, test_db):
        now = _now()
        for n in range(5):
            await _add(test_db, _NET + "10", now - timedelta(minutes=n + 1), f"p{n}")

        seen, cursor, pages = [], None, 0
        while True:
            params = {"device_ip": _NET + "10", "limit": 2}
            if cursor:
                params["cursor"] = cursor
            body = (await _get(async_client, superadmin_token, **params)).json()
            assert "total" not in body
            seen += [e["message"] for e in body["events"]]
            pages += 1
            cursor = body["next_cursor"]
            assert body["has_more"] is (cursor is not None)
            if not body["has_more"]:
                break
        assert seen == ["p0", "p1", "p2", "p3", "p4"]
        assert pages == 3

    async def test_events_with_the_same_timestamp_are_not_skipped(
        self, async_client, superadmin_token, test_db
    ):
        same = _now() - timedelta(minutes=30)
        ids = [await _add(test_db, _NET + "11", same, f"t{n}") for n in range(3)]

        first = (await _get(async_client, superadmin_token, device_ip=_NET + "11", limit=2)).json()
        second = (
            await _get(
                async_client, superadmin_token, device_ip=_NET + "11", limit=2,
                cursor=first["next_cursor"],
            )
        ).json()
        got = [e["id"] for e in first["events"] + second["events"]]
        assert got == sorted(ids, reverse=True)
        assert second["has_more"] is False

    async def test_invalid_cursor_is_rejected(self, async_client, superadmin_token):
        resp = await _get(async_client, superadmin_token, cursor="not-a-cursor")
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Invalid cursor."


class TestFilters:
    async def test_device_ip_prefix_matches_and_wildcards_are_literal(
        self, async_client, superadmin_token, test_db
    ):
        now = _now() - timedelta(minutes=5)
        await _add(test_db, _NET + "20", now, "a")
        await _add(test_db, _NET + "21", now, "b")

        resp = await _get(async_client, superadmin_token, device_ip=_NET + "2")
        assert {"a", "b"} <= {e["message"] for e in resp.json()["events"]}
        # "_" and "%" are not wildcards: "203_0" must not match "203.0".
        resp = await _get(async_client, superadmin_token, device_ip="203_0.113.2")
        assert resp.json()["events"] == []

    async def test_message_filter_is_case_insensitive_substring(
        self, async_client, superadmin_token, test_db
    ):
        await _add(test_db, _NET + "30", _now() - timedelta(minutes=5), "Link DOWN on ether2")
        resp = await _get(async_client, superadmin_token, device_ip=_NET + "30", message="link down")
        assert [e["message"] for e in resp.json()["events"]] == ["Link DOWN on ether2"]

    async def test_severity_filter_still_applies(self, async_client, superadmin_token, test_db):
        now = _now() - timedelta(minutes=5)
        await _add(test_db, _NET + "31", now, "notice", severity=5)
        await _add(test_db, _NET + "31", now, "info", severity=6)
        resp = await _get(async_client, superadmin_token, device_ip=_NET + "31", severity=5)
        assert [e["message"] for e in resp.json()["events"]] == ["notice"]

    async def test_requires_authentication(self, async_client):
        assert (await async_client.get("/syslog")).status_code == 401
