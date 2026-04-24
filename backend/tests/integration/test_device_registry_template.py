"""Tests for device-registry bulk template CSV generation."""

import csv
import io

import pytest
from httpx import AsyncClient
from sqlalchemy import delete


pytestmark = pytest.mark.asyncio


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_bulk_template_returns_csv(
    async_client: AsyncClient, admin_token: str
):
    """Template endpoint must return CSV Content-Type and .csv filename."""
    resp = await async_client.get(
        "/device-registry/bulk/template",
        headers=_auth(admin_token),
    )

    assert resp.status_code == 200
    assert (
        "text/csv" in resp.headers.get("content-type", "")
    ), f"Expected text/csv content-type, got: {resp.headers.get('content-type')}"
    assert (
        "device_registry_bulk_template.csv"
        in resp.headers.get("content-disposition", "")
    ), f"Expected .csv filename, got: {resp.headers.get('content-disposition')}"


async def test_template_csv_has_correct_headers_and_example_rows(
    async_client: AsyncClient, admin_token: str
):
    """CSV must have required headers: mac, name, description, category_id, nas_ip."""
    resp = await async_client.get(
        "/device-registry/bulk/template",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    text = resp.content.decode("utf-8-sig")

    import csv
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    # Find the actual data header row (skip # comment lines)
    data_header_idx = None
    for i, row in enumerate(rows):
        if row and not row[0].startswith("#"):
            data_header_idx = i
            break

    assert data_header_idx is not None, "No data header found after comment lines"
    headers = rows[data_header_idx]
    assert headers == [
        "mac",
        "name",
        "description",
        "category_id",
        "nas_ip",
    ], f"CSV headers mismatch: {headers}"

    # Example rows must be after header row
    assert len(rows) > data_header_idx + 1, "No example rows found after header"

    # Verify at least one example row has non-empty mac
    example_rows = rows[data_header_idx + 1 :]
    first_example = example_rows[0]
    assert first_example[0] is not None and str(first_example[0]).strip() != "", (
        "First example row must have a non-empty mac address"
    )


async def test_template_csv_contains_category_reference(
    async_client: AsyncClient,
    admin_token: str,
    test_db,
):
    """CSV template must contain category reference in comment lines."""
    from app.models.models import NasCategory

    # Seed two categories
    cat1 = NasCategory(name="Residential AP", description="Standard home routers")
    cat2 = NasCategory(name="Enterprise AP", description="High-capacity sector")
    test_db.add_all([cat1, cat2])
    await test_db.commit()

    try:
        resp = await async_client.get(
            "/device-registry/bulk/template",
            headers=_auth(admin_token),
        )
        assert resp.status_code == 200

        text = resp.content.decode("utf-8-sig")

        # Should NOT contain comment rows - CSV must be parseable directly
        assert "Categories available:" not in text, (
            "CSV template must not contain comment rows that break DictReader parsing"
        )

        # Must be valid parseable CSV with correct headers
        reader = csv.DictReader(io.StringIO(text))
        assert set(reader.fieldnames) == {"mac", "name", "description", "category_id", "nas_ip"}
    finally:
        await test_db.execute(
            delete(NasCategory).where(NasCategory.name.in_(["Residential AP", "Enterprise AP"]))
        )
        await test_db.commit()


async def test_template_csv_has_no_serial_number_field(
    async_client: AsyncClient, admin_token: str
):
    """CSV template must NOT contain serial_number column — MAC is the unique identifier."""
    resp = await async_client.get(
        "/device-registry/bulk/template",
        headers=_auth(admin_token),
    )
    assert resp.status_code == 200

    text = resp.content.decode("utf-8-sig")
    lines = text.splitlines()

    # Find the data header row
    data_header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            continue
        if line.strip():
            data_header_idx = i
            break

    assert data_header_idx is not None

    import csv
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    headers = rows[data_header_idx]

    assert "serial_number" not in headers, (
        f"CSV template must NOT have serial_number column, found headers: {headers}"
    )


async def test_bulk_csv_endpoint_normalizes_mac_formats(
    async_client: AsyncClient, admin_token: str, test_db
):
    """MAC addresses in various formats should be normalized to lowercase 12-char hex."""
    from app.models.models import DeviceRegistry

    # Clean up any existing test devices
    await test_db.execute(
        delete(DeviceRegistry).where(
            DeviceRegistry.mac.in_(["0a003e45764a", "1b003e45764b"])
        )
    )
    await test_db.commit()

    try:
        # Upload CSV with mixed MAC formats (all required fields provided)
        csv_content = """mac,name,description,category_id,nas_ip
0A:00:3E:45:76:4A,Device Colons,Test device colons,,192.168.1.10
1B-00-3E-45-76-4B,Device Dashes,Test device dashes,,192.168.1.11
1c00.3e45.764c,Device Dots,Test device dots,,192.168.1.12
1D003E45764D,Device Plain,Test device plain,,192.168.1.13
"""
        resp = await async_client.post(
            "/device-registry/bulk/csv",
            headers=_auth(admin_token),
            files={"file": ("devices.csv", csv_content.encode("utf-8"), "text/csv")},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["created"] == 4, f"Expected 4 created, got {result}"
        assert len(result["errors"]) == 0, f"Unexpected errors: {result['errors']}"

        # Verify all MACs were normalized to lowercase 12-char hex
        from sqlalchemy import select

        for normalized_mac in ["0a003e45764a", "1b003e45764b", "1c003e45764c", "1d003e45764d"]:
            result_row = await test_db.execute(
                select(DeviceRegistry).where(DeviceRegistry.mac == normalized_mac)
            )
            device = result_row.scalars().first()
            assert device is not None, f"MAC {normalized_mac} not found in DB — normalization failed"
    finally:
        await test_db.execute(
            delete(DeviceRegistry).where(
                DeviceRegistry.mac.in_(["0a003e45764a", "1b003e45764b", "1c003e45764c", "1d003e45764d"])
            )
        )
        await test_db.commit()
