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


async def _group(test_db, name: str) -> str:
    from app.models.models import RadGroupReply

    test_db.add(RadGroupReply(groupname=name, attribute="Reply-Message", op=":=", value=name))
    await test_db.commit()
    return name


async def _listed(client, token, username):
    resp = await client.get("/access-policies/assignments", params={"username": username}, headers=_auth(token))
    return {r["id"]: r for r in resp.json()}


async def _audit_rows(test_db, username, action):
    test_db.expire_all()
    rows = (
        await test_db.execute(select(AppAuditLog).where(AppAuditLog.target_user == username))
    ).scalars().all()
    return [r for r in rows if r.action.endswith(action)]


class TestBulkUpdate:
    async def test_bulk_update_changes_only_requested_fields(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        user = _user()
        group = await _group(test_db, f"grp_{uuid.uuid4().hex[:6]}")
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.2.1", "10.97.2.2", "10.97.2.3"])
        ids = [r["id"] for r in rows[:2]]
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": ids, "radius_group": group, "privilege_level": "1", "review_date": "2031-03-15"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        assert sorted(r["id"] for r in resp.json()) == sorted(ids)

        listed = await _listed(async_client, superadmin_token, user)
        for i in ids:
            assert listed[i]["radius_group"] == group
            assert listed[i]["privilege_level"] == "1"
            assert listed[i]["review_date"] == "2031-03-15"
            assert listed[i]["nas_ip"] == next(r["nas_ip"] for r in rows if r["id"] == i)
            assert listed[i]["is_active"] == 1
        untouched = listed[rows[2]["id"]]
        assert (untouched["radius_group"], untouched["privilege_level"]) == ("network_admins", "15")

    async def test_bulk_update_writes_one_audit_entry_per_row(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.3.1", "10.97.3.2"])
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [r["id"] for r in rows], "is_active": 0},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text
        entries = await _audit_rows(test_db, user, "BULK_UPDATE")
        assert len(entries) == 2
        assert all(e.admin_user == "test_superadmin" for e in entries)
        assert all('"is_active": 1' in e.old_value and '"is_active": 0' in e.new_value for e in entries)

    async def test_unknown_group_rejects_whole_batch(self, async_client: AsyncClient, superadmin_token: str):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.4.1"])
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [rows[0]["id"]], "radius_group": "does-not-exist-97"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422
        assert "does-not-exist-97" in resp.json()["detail"]
        listed = await _listed(async_client, superadmin_token, user)
        assert listed[rows[0]["id"]]["radius_group"] == "network_admins"

    async def test_unknown_id_rejects_whole_batch(self, async_client: AsyncClient, superadmin_token: str):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.5.1"])
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [rows[0]["id"], 99999999], "privilege_level": "1"},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 404
        listed = await _listed(async_client, superadmin_token, user)
        assert listed[rows[0]["id"]]["privilege_level"] == "15"

    @pytest.mark.parametrize("body", [{"ids": []}, {"ids": [1]}, {"ids": [1], "is_active": 5}])
    async def test_invalid_payload_is_422(self, async_client: AsyncClient, superadmin_token: str, body):
        resp = await async_client.patch(
            "/access-policies/assignments/bulk", json=body, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 422

    async def test_reactivating_category_rows_respects_single_active_rule(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        user = _user()
        cat = await _category(async_client, superadmin_token)
        cat2 = await _category(async_client, superadmin_token)
        test_db.add_all(
            [
                AccessPolicyAssignment(username=user, nas_category_id=cat["id"], radius_group="g1", is_active=1),
                AccessPolicyAssignment(username=user, nas_category_id=cat2["id"], radius_group="g1", is_active=0),
            ]
        )
        await test_db.commit()
        listed = await _listed(async_client, superadmin_token, user)
        inactive_id = next(i for i, r in listed.items() if r["is_active"] == 0)
        # Reactivating a row whose category has no other active row is fine.
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [inactive_id], "is_active": 1},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 200, resp.text

    async def test_reactivation_conflict_rejects_batch(self, async_client: AsyncClient, superadmin_token: str, test_db):
        user = _user()
        cat = await _category(async_client, superadmin_token)
        test_db.add(AccessPolicyAssignment(username=user, nas_category_id=cat["id"], radius_group="g1", is_active=1))
        await test_db.commit()
        # A second, inactive row in the same category can only exist as legacy
        # data (the ORM target_key prevents it), so insert it with raw SQL.
        from sqlalchemy import text

        await test_db.execute(
            text(
                "INSERT INTO access_policy_assignments (username, target_key, segment_target_key, nas_category_id, radius_group, is_active) "
                "VALUES (:u, :k, '', :c, 'g1', 0)"
            ),
            {"u": user, "k": uuid.uuid4().hex * 2, "c": cat["id"]},
        )
        await test_db.commit()
        listed = await _listed(async_client, superadmin_token, user)
        dup_id = next(i for i, r in listed.items() if r["is_active"] == 0)
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [dup_id], "is_active": 1},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 409

    @pytest.mark.parametrize("token_fixture", ["helpdesk_token", "auditor_token"])
    async def test_only_admins_can_bulk_update(
        self, async_client: AsyncClient, superadmin_token: str, token_fixture, request
    ):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.6.1"])
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [rows[0]["id"]], "privilege_level": "1"},
            headers=_auth(request.getfixturevalue(token_fixture)),
        )
        assert resp.status_code == 403


class TestBulkDelete:
    async def test_superadmin_bulk_delete_with_per_row_audit(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.7.1", "10.97.7.2", "10.97.7.3"])
        ids = [r["id"] for r in rows[:2]]
        resp = await async_client.post(
            "/access-policies/assignments/bulk-delete", json={"ids": ids}, headers=_auth(superadmin_token)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"deleted": 2}
        listed = await _listed(async_client, superadmin_token, user)
        assert set(listed) == {rows[2]["id"]}
        assert len(await _audit_rows(test_db, user, "BULK_DELETE")) == 2

    async def test_admin_cannot_bulk_delete(self, async_client: AsyncClient, superadmin_token: str, admin_token: str):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.8.1"])
        resp = await async_client.post(
            "/access-policies/assignments/bulk-delete", json={"ids": [rows[0]["id"]]}, headers=_auth(admin_token)
        )
        assert resp.status_code == 403
        assert set(await _listed(async_client, superadmin_token, user)) == {rows[0]["id"]}

    async def test_unknown_id_deletes_nothing(self, async_client: AsyncClient, superadmin_token: str):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.9.1"])
        resp = await async_client.post(
            "/access-policies/assignments/bulk-delete",
            json={"ids": [rows[0]["id"], 99999999]},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 404
        assert set(await _listed(async_client, superadmin_token, user)) == {rows[0]["id"]}


class TestVerifierFollowUps:
    @pytest.mark.parametrize("field", ["is_active", "radius_group"])
    async def test_explicit_null_is_rejected(self, async_client: AsyncClient, superadmin_token: str, field):
        user = _user()
        rows = await _bulk_ip(async_client, superadmin_token, user, ["10.97.10.1"])
        resp = await async_client.patch(
            "/access-policies/assignments/bulk",
            json={"ids": [rows[0]["id"]], field: None},
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 422

    async def test_put_inactive_category_row_with_active_sibling_still_409(
        self, async_client: AsyncClient, superadmin_token: str, test_db
    ):
        """Previous behavior kept (main returned 409 regardless of is_active)."""
        from sqlalchemy import text

        user = _user()
        cat = await _category(async_client, superadmin_token)
        test_db.add(AccessPolicyAssignment(username=user, nas_category_id=cat["id"], radius_group="g1", is_active=1))
        await test_db.commit()
        await test_db.execute(
            text(
                "INSERT INTO access_policy_assignments (username, target_key, segment_target_key, nas_category_id, radius_group, is_active) "
                "VALUES (:u, :k, '', :c, 'g1', 0)"
            ),
            {"u": user, "k": uuid.uuid4().hex * 2, "c": cat["id"]},
        )
        await test_db.commit()
        listed = await _listed(async_client, superadmin_token, user)
        inactive = next(r for r in listed.values() if r["is_active"] == 0)
        resp = await async_client.put(
            f"/access-policies/assignments/{inactive['id']}",
            json=_edit_payload(inactive, privilege_level="3"),
            headers=_auth(superadmin_token),
        )
        assert resp.status_code == 409
        assert "active assignment in this category" in resp.json()["detail"]
