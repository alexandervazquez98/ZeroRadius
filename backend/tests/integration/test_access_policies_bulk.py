"""Access policy assignments: single-edit fixes and bulk management (#97).

Spec: odd/tasks/access-policies-bulk-edit.md (S1-S6).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import AccessPolicyAssignment, AppAuditLog


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.limiter import limiter

    limiter.reset()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _user() -> str:
    return f"ap_{uuid.uuid4().hex[:8]}"


async def _bulk_ip(client: AsyncClient, token: str, username: str, ips: list[str], **extra) -> list[dict]:
    payload = {"username": username, "nas_ips": ips, "radius_group": "network_admins", "privilege_level": "15"}
    payload.update(extra)
    resp = await client.post("/access-policies/assignments/bulk", json=payload, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _category(client: AsyncClient, token: str) -> dict:
    resp = await client.post(
        "/nas-categories",
        json={"name": f"BulkCat_{uuid.uuid4().hex[:8]}", "criticality": "standard"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _edit_payload(row: dict, **changes) -> dict:
    """Full PUT payload built from a listed row, as the UI does."""
    fields = (
        "username", "nas_ip", "calling_station_id", "nas_category_id", "segment_id",
        "target_start_ip", "target_end_ip", "nas_identifier", "nas_vendor", "radius_group",
        "privilege_level", "justification", "approved_by", "review_date", "is_active", "cir_id",
    )
    payload = {k: row.get(k) for k in fields}
    payload.update(changes)
    return payload


class TestSingleEditFixes:
    async def test_regression_edit_ip_row_when_user_has_other_ip_rows(
        self, async_client: AsyncClient, superadmin_token: str
    ):
        """S5: editing one of several IP rows of a user must not return 409."""
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.0.1", "10.97.0.2"])
        resp = await async_client.put(
            f"/access-policies/assignments/{rows[0]['id']}",
            json=_edit_payload(rows[0], privilege_level="1"),
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["privilege_level"] == "1"

    async def test_category_rule_still_rejects_second_active_row_in_same_category(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        """Previous behavior kept: one active assignment per user per category."""
        user = _user()
        cat_x = await _category(async_client, superadmin_token)
        cat_y = await _category(async_client, superadmin_token)
        test_db.add_all(
            [
                AccessPolicyAssignment(username=user, nas_category_id=cat_x["id"], radius_group="g1", is_active=1),
                AccessPolicyAssignment(username=user, nas_category_id=cat_y["id"], radius_group="g1", is_active=1),
            ]
        )
        await test_db.commit()
        listed = (
            await async_client.get(
                "/access-policies/assignments", params={"username": user}, headers=_auth(superadmin_token)
            )
        ).json()
        row_y = next(r for r in listed if r["nas_category_id"] == cat_y["id"])
        resp = await async_client.put(
            f"/access-policies/assignments/{row_y['id']}",
            json=_edit_payload(row_y, nas_category_id=cat_x["id"]),
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 409, resp.text

    async def test_regression_edit_keeps_cir_and_nas_identifier_when_sent(
        self, async_client: AsyncClient, superadmin_token: str
    ):
        """S6 (API side): a full payload with cir/nas_identifier keeps them."""
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.1.1"])
        resp = await async_client.put(
            f"/access-policies/assignments/{rows[0]['id']}",
            json=_edit_payload(rows[0], nas_identifier="sw-core-97"),
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["nas_identifier"] == "sw-core-97"
        resp = await async_client.put(
            f"/access-policies/assignments/{rows[0]['id']}",
            json=_edit_payload(resp.json(), privilege_level="7"),
            headers=_auth(superadmin_token),
        )
        assert resp.json()["nas_identifier"] == "sw-core-97"
