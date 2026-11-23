"""
Integration tests: GET /syslog/nas-status.

A registered NAS counts as silent when no syslog event arrived from it within
the threshold (default 24 h). The session-scoped test DB is shared with other
tests, so assertions target this module's own NAS rows (198.51.100.0/24).
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.models import Nas, SyslogEvent

_SECRET = "s" * 32
_PREFIX = "198.51."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _ensure_nas(db, nasname, shortname):
    # Inserted directly: POST /nas is rate-limited to 10/minute.
    exists = await db.execute(select(Nas.id).where(Nas.nasname == nasname))
    if exists.first() is None:
        db.add(Nas(nasname=nasname, shortname=shortname, secret=_SECRET, type="other"))
        await db.commit()


async def _add_event(db, device_ip, received_at):
    # Inserted directly with an explicit id: SQLite does not autoincrement the
    # BIGINT primary key, so POST /syslog/ingest cannot run on the test DB.
    next_id = (await db.execute(select(func.coalesce(func.max(SyslogEvent.id), 0)))).scalar() + 1
    db.add(
        SyslogEvent(
            id=next_id,
            received_at=received_at,
            device_ip=device_ip,
            facility=16,
            severity=6,
            program="test",
            message=f"nas-status probe from {device_ip}",
        )
    )
    await db.commit()


@pytest.fixture
async def seeded(async_client, test_db):
    await _ensure_nas(test_db, "198.51.100.11", "ns-recent")
    await _ensure_nas(test_db, "198.51.100.12", "ns-stale")
    await _ensure_nas(test_db, "198.51.100.13", "ns-never")
    await _ensure_nas(test_db, "198.51.101.0/29", "ns-cidr")
    now = _now()
    await _add_event(test_db, "198.51.100.11", now - timedelta(hours=1))
    await _add_event(test_db, "198.51.100.12", now - timedelta(hours=30))
    await _add_event(test_db, "198.51.101.3", now - timedelta(minutes=5))
    # Unregistered device: must not appear in the report.
    await _add_event(test_db, "198.51.100.99", now)
    return now


def _ours(body):
    return {d["nasname"]: d for d in body["devices"] if d["nasname"].startswith(_PREFIX)}


class TestNasSyslogStatus:
    async def test_reports_silent_and_reporting_nas(self, async_client, superadmin_token, seeded):
        resp = await async_client.get(
            "/syslog/nas-status", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["threshold_hours"] == 24

        ours = _ours(body)
        assert set(ours) == {"198.51.100.11", "198.51.100.12", "198.51.100.13", "198.51.101.0/29"}
        assert ours["198.51.100.11"]["silent"] is False
        assert ours["198.51.100.12"]["silent"] is True
        assert ours["198.51.100.12"]["last_seen"] is not None
        assert ours["198.51.100.13"]["silent"] is True
        assert ours["198.51.100.13"]["last_seen"] is None
        # CIDR NAS reports when any address in its network sent syslog.
        assert ours["198.51.101.0/29"]["silent"] is False
        assert ours["198.51.101.0/29"]["shortname"] == "ns-cidr"

        assert body["total"] == len(body["devices"])
        assert body["silent_count"] == sum(1 for d in body["devices"] if d["silent"])
        assert body["reporting_count"] == body["total"] - body["silent_count"]

    async def test_silent_nas_listed_first(self, async_client, superadmin_token, seeded):
        resp = await async_client.get(
            "/syslog/nas-status", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        flags = [d["silent"] for d in resp.json()["devices"]]
        assert flags == sorted(flags, reverse=True)

    async def test_hours_query_overrides_threshold(self, async_client, superadmin_token, seeded):
        resp = await async_client.get(
            "/syslog/nas-status",
            params={"hours": 48},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["threshold_hours"] == 48
        assert _ours(body)["198.51.100.12"]["silent"] is False

    async def test_threshold_from_env(self, async_client, superadmin_token, seeded, monkeypatch):
        monkeypatch.setenv("SYSLOG_SILENT_HOURS", "36")
        resp = await async_client.get(
            "/syslog/nas-status", headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        body = resp.json()
        assert body["threshold_hours"] == 36
        assert _ours(body)["198.51.100.12"]["silent"] is False

    async def test_rejects_invalid_hours(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/syslog/nas-status",
            params={"hours": 0},
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 422

    async def test_readonly_user_can_read(self, async_client, readonly_token):
        resp = await async_client.get(
            "/syslog/nas-status", headers={"Authorization": f"Bearer {readonly_token}"}
        )
        assert resp.status_code == 200

    async def test_unauthenticated_rejected(self, async_client):
        resp = await async_client.get("/syslog/nas-status")
        assert resp.status_code in (401, 403)
