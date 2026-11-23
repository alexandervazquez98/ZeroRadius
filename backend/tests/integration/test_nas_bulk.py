"""Bulk NAS registration by CSV: POST /nas/bulk/csv and GET /nas/bulk/template.

Spec: odd/tasks (T3, S2) — per-row validation identical to POST /nas, upsert by
nasname (nasname is not unique, #98), dry run, no RADIUS restart, no secrets in
responses or audit.
"""

import csv
import io
import json
import random
import uuid
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import AppAuditLog, Nas, NasCategory


SECRET_A = "bulk-secret-a-" + "x" * 30  # 44 chars
SECRET_B = "bulk-secret-b-" + "y" * 30  # 44 chars
HEADER = "nasname,shortname,secret,category,type,description"


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core.limiter import limiter

    limiter.reset()


@pytest.fixture(autouse=True)
def _no_radius_restart(monkeypatch):
    """The bulk endpoint must never restart FreeRADIUS (no Docker access at all)."""
    import docker

    calls: list[int] = []
    monkeypatch.setattr(docker, "from_env", lambda *a, **k: calls.append(1))
    yield calls


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ip() -> str:
    return f"10.{random.randint(150, 250)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _csv(*rows: str, header: str = HEADER) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


async def _upload(client: AsyncClient, token: str, content: bytes, **params):
    return await client.post(
        "/nas/bulk/csv",
        params=params,
        files={"file": ("nas.csv", content, "text/csv")},
        headers=_auth(token),
    )


async def _rows(db, nasname: str) -> list[Nas]:
    db.expire_all()
    result = await db.execute(select(Nas).where(Nas.nasname == nasname).order_by(Nas.id))
    return list(result.scalars().all())


async def _category(db, name: str | None = None) -> SimpleNamespace:
    """Insert a category; return plain values so later expire_all() cannot lazy-load."""
    cat = NasCategory(name=name or f"BULK_{uuid.uuid4().hex[:8]}", criticality="standard")
    db.add(cat)
    await db.commit()
    await db.refresh(cat)
    return SimpleNamespace(id=cat.id, name=cat.name)


async def _seed_nas(db, nasname: str, **fields) -> Nas:
    nas = Nas(
        nasname=nasname,
        shortname=fields.get("shortname", "seed"),
        secret=fields.get("secret", SECRET_A),
        type=fields.get("type", "cisco"),
        description=fields.get("description", "seeded"),
        category_id=fields.get("category_id"),
    )
    db.add(nas)
    await db.commit()
    await db.refresh(nas)
    return nas


def _assert_no_secret(resp, *secrets: str) -> None:
    for secret in secrets:
        assert secret not in resp.text


# ── create ────────────────────────────────────────────────────────────────────


async def test_bulk_csv_creates_rows_with_category_and_no_restart(
    async_client, admin_token, test_db, _no_radius_restart
):
    cat = await _category(test_db)
    ip1, ip2 = _ip(), "10.149.0.0/24"
    resp = await _upload(
        async_client,
        admin_token,
        _csv(
            f"{ip1},AP-1,{SECRET_A},{cat.name},cisco,Branch 1 AP",
            f"{ip2},AP-NET,{SECRET_B},,,",
        ),
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 2, "updated": 0, "errors": [], "dry_run": False}
    _assert_no_secret(resp, SECRET_A, SECRET_B)

    [row1] = await _rows(test_db, ip1)
    assert (row1.shortname, row1.secret, row1.category_id, row1.type, row1.description) == (
        "AP-1", SECRET_A, cat.id, "cisco", "Branch 1 AP"
    )
    [row2] = await _rows(test_db, ip2)
    assert row2.secret == SECRET_B
    assert row2.category_id is None
    assert row2.type == "other"
    assert _no_radius_restart == []


async def test_bulk_csv_writes_one_audit_entry_without_secrets(async_client, admin_token, test_db):
    resp = await _upload(async_client, admin_token, _csv(f"{_ip()},,{SECRET_A},,,"))
    assert resp.status_code == 200

    test_db.expire_all()
    entry = (
        await test_db.execute(
            select(AppAuditLog)
            .where(AppAuditLog.table_affected == "nas")
            .order_by(AppAuditLog.id.desc())
        )
    ).scalars().first()
    assert entry is not None
    assert "BULK_CSV" in entry.action
    assert entry.admin_user == "test_admin"
    payload = json.loads(entry.new_value)
    assert payload["created"] == 1 and payload["updated"] == 0 and payload["errors"] == 0
    assert SECRET_A not in (entry.new_value or "") + (entry.old_value or "")


# ── update / duplicates ──────────────────────────────────────────────────────


async def test_bulk_csv_updates_single_existing_nasname_and_keeps_empty_cells(
    async_client, admin_token, test_db
):
    cat = await _category(test_db)
    ip = _ip()
    seeded_id = (await _seed_nas(test_db, ip, shortname="old", type="cisco", description="keep me")).id

    resp = await _upload(
        async_client, admin_token, _csv(f"{ip},new-short,{SECRET_B},{cat.name},,")
    )

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"created": 0, "updated": 1, "errors": [], "dry_run": False}
    [row] = await _rows(test_db, ip)
    assert row.id == seeded_id
    assert (row.shortname, row.secret, row.category_id) == ("new-short", SECRET_B, cat.id)
    assert (row.type, row.description) == ("cisco", "keep me")


async def test_bulk_csv_nasname_matching_several_rows_is_row_error(
    async_client, admin_token, test_db
):
    ip = _ip()
    await _seed_nas(test_db, ip)
    await _seed_nas(test_db, ip)

    resp = await _upload(async_client, admin_token, _csv(f"{ip},x,{SECRET_B},,,"))

    body = resp.json()
    assert resp.status_code == 200
    assert body["created"] == 0 and body["updated"] == 0
    assert len(body["errors"]) == 1
    assert body["errors"][0]["row"] == 1
    assert body["errors"][0]["nasname"] == ip
    assert "multiple" in body["errors"][0]["error"].lower()
    rows = await _rows(test_db, ip)
    assert [r.secret for r in rows] == [SECRET_A, SECRET_A]


async def test_bulk_csv_duplicate_nasname_in_file_is_error_for_later_rows(
    async_client, admin_token, test_db
):
    ip = _ip()
    resp = await _upload(
        async_client,
        admin_token,
        _csv(f"{ip},first,{SECRET_A},,,", f"{ip},second,{SECRET_B},,,", f"{ip},third,{SECRET_B},,,"),
    )

    body = resp.json()
    assert body["created"] == 1
    assert [e["row"] for e in body["errors"]] == [2, 3]
    assert all("duplicate" in e["error"].lower() for e in body["errors"])
    [row] = await _rows(test_db, ip)
    assert row.shortname == "first"


# ── per-row validation (same rules as POST /nas) ─────────────────────────────


async def test_bulk_csv_row_validation_errors(async_client, admin_token, test_db):
    good = _ip()
    short_secret = "short-secret-123"
    long_secret = "z" * 61
    rows = [
        f"{good},ok,{SECRET_A},,,",  # 1 valid
        f"not a host!,bad,{SECRET_A},,,",  # 2 bad IP/hostname
        f"{_ip()},short,{short_secret},,,",  # 3 short secret
        f"{_ip()},long,{long_secret},,,",  # 4 secret > 60
        f"{_ip()},cat,{SECRET_A},NO_SUCH_CATEGORY_XYZ,,",  # 5 unknown category
        f",empty,{SECRET_A},,,",  # 6 missing nasname
    ]
    resp = await _upload(async_client, admin_token, _csv(*rows))

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1 and body["updated"] == 0
    errors = {e["row"]: e for e in body["errors"]}
    assert sorted(errors) == [2, 3, 4, 5, 6]
    assert "nasname" in errors[2]["error"]
    assert "32" in errors[3]["error"]
    assert "60" in errors[4]["error"]
    assert "NO_SUCH_CATEGORY_XYZ" in errors[5]["error"]
    assert errors[6]["nasname"] is None
    _assert_no_secret(resp, SECRET_A, short_secret, long_secret)
    assert len(await _rows(test_db, good)) == 1


async def test_bulk_csv_default_category_id_applies_to_empty_category(
    async_client, admin_token, test_db
):
    default_cat = await _category(test_db)
    other_cat = await _category(test_db)
    ip1, ip2 = _ip(), _ip()

    resp = await _upload(
        async_client,
        admin_token,
        _csv(f"{ip1},,{SECRET_A},,,", f"{ip2},,{SECRET_A},{other_cat.name},,"),
        default_category_id=default_cat.id,
    )

    assert resp.json()["created"] == 2
    assert (await _rows(test_db, ip1))[0].category_id == default_cat.id
    assert (await _rows(test_db, ip2))[0].category_id == other_cat.id


async def test_bulk_csv_unknown_default_category_id_is_422(async_client, admin_token):
    resp = await _upload(
        async_client, admin_token, _csv(f"{_ip()},,{SECRET_A},,,"), default_category_id=999999
    )
    assert resp.status_code == 422


# ── dry run ──────────────────────────────────────────────────────────────────


async def test_bulk_csv_dry_run_reports_and_writes_nothing(async_client, admin_token, test_db):
    new_ip, existing_ip = _ip(), _ip()
    await _seed_nas(test_db, existing_ip, shortname="before")
    test_db.expire_all()
    audits_before = len((await test_db.execute(select(AppAuditLog))).scalars().all())

    resp = await _upload(
        async_client,
        admin_token,
        _csv(f"{new_ip},n,{SECRET_A},,,", f"{existing_ip},after,{SECRET_B},,,", f"bad host,,{SECRET_A},,,"),
        dry_run="true",
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["created"], body["updated"], body["dry_run"]) == (1, 1, True)
    assert [e["row"] for e in body["errors"]] == [3]
    assert await _rows(test_db, new_ip) == []
    [existing] = await _rows(test_db, existing_ip)
    assert (existing.shortname, existing.secret) == ("before", SECRET_A)
    test_db.expire_all()
    assert len((await test_db.execute(select(AppAuditLog))).scalars().all()) == audits_before


# ── file-level rejections ────────────────────────────────────────────────────


async def test_bulk_csv_missing_required_headers_is_422(async_client, admin_token):
    resp = await _upload(
        async_client, admin_token, _csv(f"{_ip()},x", header="nasname,shortname")
    )
    assert resp.status_code == 422
    assert "secret" in resp.json()["detail"]


async def test_bulk_csv_file_larger_than_1mb_is_413(async_client, admin_token):
    big = _csv(*[f"{_ip()},,{SECRET_A},,," + "d" * 200 for _ in range(5000)])
    assert len(big) > 1024 * 1024
    resp = await _upload(async_client, admin_token, big)
    assert resp.status_code == 413


async def test_bulk_csv_more_than_5000_rows_is_422(async_client, admin_token, test_db):
    content = _csv(*["1.1.1.1,,s,,," for _ in range(5001)])
    assert len(content) < 1024 * 1024
    resp = await _upload(async_client, admin_token, content)
    assert resp.status_code == 422
    assert "5000" in resp.json()["detail"]
    assert await _rows(test_db, "1.1.1.1") == []


async def test_bulk_csv_utf8_bom_is_accepted(async_client, admin_token, test_db):
    ip = _ip()
    resp = await _upload(async_client, admin_token, b"\xef\xbb\xbf" + _csv(f"{ip},,{SECRET_A},,,"))
    assert resp.json()["created"] == 1
    assert len(await _rows(test_db, ip)) == 1


# ── RBAC ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("token_name", ["readonly_token", "helpdesk_token", "auditor_token"])
async def test_bulk_csv_forbidden_for_non_admin_roles(async_client, request, test_db, token_name):
    ip = _ip()
    token = request.getfixturevalue(token_name)
    resp = await _upload(async_client, token, _csv(f"{ip},,{SECRET_A},,,"))
    assert resp.status_code == 403
    assert await _rows(test_db, ip) == []


async def test_bulk_csv_allowed_for_superadmin(async_client, superadmin_token, test_db):
    ip = _ip()
    resp = await _upload(async_client, superadmin_token, _csv(f"{ip},,{SECRET_A},,,"))
    assert resp.status_code == 200
    assert resp.json()["created"] == 1


@pytest.mark.parametrize("token_name", ["readonly_token", "helpdesk_token"])
async def test_bulk_template_forbidden_for_non_admin_roles(async_client, request, token_name):
    resp = await async_client.get(
        "/nas/bulk/template", headers=_auth(request.getfixturevalue(token_name))
    )
    assert resp.status_code == 403


# ── template ─────────────────────────────────────────────────────────────────


async def test_bulk_template_content(async_client, admin_token):
    resp = await async_client.get("/nas/bulk/template", headers=_auth(admin_token))

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(resp.text)))
    assert list(rows[0].keys()) == ["nasname", "shortname", "secret", "category", "type", "description"]
    assert len(rows) == 2
    for row in rows:
        assert row["nasname"].startswith(("192.0.2.", "198.51.100."))
        assert len(row["secret"]) >= 32
        assert len(row["secret"]) <= 60


async def test_bulk_template_rows_pass_dry_run_validation(async_client, admin_token):
    template = await async_client.get("/nas/bulk/template", headers=_auth(admin_token))
    # Strip category names so the check does not depend on seeded categories.
    rows = list(csv.DictReader(io.StringIO(template.text)))
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "category": ""})
    resp = await _upload(async_client, admin_token, out.getvalue().encode(), dry_run="true")
    assert resp.json()["errors"] == []


# ── existing POST /nas still works (shares NasCreate) ────────────────────────


async def test_existing_post_nas_still_validates_and_creates(async_client, admin_token, test_db):
    ip = _ip()
    short = await async_client.post(
        "/nas", json={"nasname": _ip(), "secret": "short"}, headers=_auth(admin_token)
    )
    assert short.status_code == 422

    ok = await async_client.post(
        "/nas",
        json={"nasname": ip, "shortname": "single", "secret": SECRET_A, "type": "other"},
        headers=_auth(admin_token),
    )
    assert ok.status_code == 200
    assert ok.json()["nasname"] == ip
    assert len(await _rows(test_db, ip)) == 1


async def test_bulk_csv_headers_are_case_insensitive(async_client, admin_token, test_db):
    """A capitalized header (e.g. Excel 'Category') must not be dropped silently."""
    cat = await _category(test_db)
    ip = _ip()
    resp = await _upload(
        async_client,
        admin_token,
        _csv(f"{ip},{SECRET_A},{cat.name},Desc", header="NASNAME,Secret,Category,Description"),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created"] == 1 and resp.json()["errors"] == []
    [row] = await _rows(test_db, ip)
    assert (row.category_id, row.description) == (cat.id, "Desc")


async def test_bulk_csv_skips_comma_only_lines_and_keeps_row_numbers(
    async_client, admin_token, test_db
):
    """Spreadsheets export empty rows as ',,,,,'; they are not data rows with errors."""
    ip1, ip2 = _ip(), _ip()
    resp = await _upload(
        async_client,
        admin_token,
        _csv(f"{ip1},,{SECRET_A},,,", ",,,,,", f"{ip2},,short,,,"),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    assert [(e["row"], e["nasname"]) for e in body["errors"]] == [(3, ip2)]
