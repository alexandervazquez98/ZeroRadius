import csv
import io

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_bulk_template_returns_expected_csv(async_client: AsyncClient, admin_token: str):
    resp = await async_client.get(
        "/device-registry/bulk/template",
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    assert (
        "text/csv"
        in resp.headers.get("content-type", "")
    )
    assert (
        "device_registry_bulk_template.csv"
        in resp.headers.get("content-disposition", "")
    )

    import csv
    import io as io_module
    content = resp.content.decode("utf-8-sig")
    reader = csv.DictReader(io_module.StringIO(content))
    assert set(reader.fieldnames) == {"mac", "name", "description", "category_id", "nas_ip"}
    rows = list(reader)
    assert len(rows) == 2  # template has 2 example rows


async def test_bulk_json_accepts_required_fields_with_optional_category(async_client: AsyncClient, admin_token: str):
    payload = {
        "devices": [
            {
                "mac": "0A:00:3E:45:76:AA",
                "nas_ip": "192.168.50.10",
                "name": "SM Torre Norte",
                "description": "Cliente premium",
                "is_active": 1,
            }
        ]
    }

    resp = await async_client.post(
        "/device-registry/bulk",
        json=payload,
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["updated"] == 0
    assert body["errors"] == []

    listed = await async_client.get("/device-registry", headers=_auth(admin_token))
    assert listed.status_code == 200
    created = next((row for row in listed.json() if row["mac"] == "0a003e4576aa"), None)
    assert created is not None
    assert created["nas_ip"] == "192.168.50.10"
    assert created["name"] == "SM Torre Norte"
    assert created["description"] == "Cliente premium"
    assert created["category_id"] is None


async def test_bulk_json_rejects_missing_new_required_fields(async_client: AsyncClient, admin_token: str):
    payload = {
        "devices": [
            {
                "mac": "0A:00:3E:45:76:AB",
                "nas_ip": "192.168.50.11",
                "name": None,
                "description": "Tiene IP pero no name",
                "is_active": 1,
            },
            {
                "mac": "0A:00:3E:45:76:AC",
                "nas_ip": "",
                "name": "SM Sin IP",
                "description": "Falta nas_ip",
                "is_active": 1,
            },
            {
                "mac": "0A:00:3E:45:76:AD",
                "nas_ip": "192.168.50.12",
                "name": "SM Sin Descripción",
                "description": "",
                "is_active": 1,
            },
        ]
    }

    resp = await async_client.post(
        "/device-registry/bulk",
        json=payload,
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 0
    assert len(body["errors"]) == 3
    assert any("missing name" in err for err in body["errors"])
    assert any("missing nas_ip" in err for err in body["errors"])
    assert any("missing description" in err for err in body["errors"])


async def test_bulk_csv_valid_row_with_name_is_imported(async_client: AsyncClient, admin_token: str):
    csv_payload = (
        "mac,nas_ip,name,description,category_id\n"
        "0A:00:3E:45:76:AE,192.168.60.10,SM CSV Norte,Importado por CSV,\n"
    )
    files = {"file": ("devices.csv", csv_payload, "text/csv")}

    resp = await async_client.post(
        "/device-registry/bulk/csv",
        files=files,
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["updated"] == 0
    assert body["errors"] == []

    listed = await async_client.get("/device-registry", headers=_auth(admin_token))
    assert listed.status_code == 200
    created = next((row for row in listed.json() if row["mac"] == "0a003e4576ae"), None)
    assert created is not None
    assert created["name"] == "SM CSV Norte"
    assert created["description"] == "Importado por CSV"


async def test_bulk_csv_rejects_example_template_mac_4a(async_client: AsyncClient, admin_token: str):
    """CSV with example MAC 0A:00:3E:45:76:4A (SM Torre Norte from template) must be rejected."""
    csv_payload = (
        "mac,nas_ip,name,description,category_id\n"
        "0A:00:3E:45:76:4A,192.168.1.11,SM Torre Norte,Cliente premium - sector norte,2\n"
    )
    files = {"file": ("devices.csv", csv_payload, "text/csv")}

    resp = await async_client.post(
        "/device-registry/bulk/csv",
        files=files,
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 0
    assert len(body["errors"]) == 1
    assert "example/template rows must be removed before import" in body["errors"][0]


async def test_bulk_csv_rejects_example_template_mac_4b(async_client: AsyncClient, admin_token: str):
    """CSV with example MAC 0A:00:3E:45:76:4B (SM Torre Sur from template) must be rejected."""
    csv_payload = (
        "mac,nas_ip,name,description,category_id\n"
        "0A:00:3E:45:76:4B,192.168.1.12,SM Torre Sur,Backhaul secundario,2\n"
    )
    files = {"file": ("devices.csv", csv_payload, "text/csv")}

    resp = await async_client.post(
        "/device-registry/bulk/csv",
        files=files,
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 0
    assert len(body["errors"]) == 1
    assert "example/template rows must be removed before import" in body["errors"][0]


async def test_bulk_csv_rejects_example_rows_mixed_with_real_data(async_client: AsyncClient, admin_token: str, test_db):
    """CSV with example rows mixed alongside real rows: example rows are rejected, real rows import."""
    from app.models.models import DeviceRegistry
    from sqlalchemy import delete

    # Clean up test MACs first
    await test_db.execute(
        delete(DeviceRegistry).where(
            DeviceRegistry.mac.in_(["0a003e45764c"])
        )
    )
    await test_db.commit()

    try:
        csv_payload = (
            "mac,nas_ip,name,description,category_id\n"
            "0A:00:3E:45:76:4A,192.168.1.11,SM Torre Norte,Cliente premium,2\n"
            "0C:00:3E:45:76:4C,192.168.1.13,SM Real,Real customer,\n"
        )
        files = {"file": ("devices.csv", csv_payload, "text/csv")}

        resp = await async_client.post(
            "/device-registry/bulk/csv",
            files=files,
            headers=_auth(admin_token),
        )

        assert resp.status_code == 200
        body = resp.json()
        # Real row is imported; example row is rejected with error
        assert body["created"] == 1
        assert len(body["errors"]) == 1
        assert "example/template rows must be removed before import" in body["errors"][0]
        # Verify the real device was actually created
        listed = await async_client.get("/device-registry", headers=_auth(admin_token))
        assert listed.status_code == 200
        created = next((row for row in listed.json() if row["mac"] == "0c003e45764c"), None)
        assert created is not None
        assert created["name"] == "SM Real"
    finally:
        await test_db.execute(
            delete(DeviceRegistry).where(
                DeviceRegistry.mac.in_(["0c003e45764c"])
            )
        )
        await test_db.commit()
