"""
Device Registry router ÔÇö device-registry feature
CRUD + bulk import for endpoint devices (SMs, CPEs) identified by MAC.
Supports CSV bulk upload and JSON bulk create.
"""

import csv
import io
import logging
import ipaddress
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request
from starlette.responses import Response

from app.core.limiter import limiter
from app.core.rbac import require_roles, Role
from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.models import AdminUser, DeviceRegistry, NasCategory
from app.schemas.device_registry import (
    DeviceRegistryCreate,
    DeviceRegistryUpdate,
    DeviceRegistryOut,
    DeviceRegistryBulkCreate,
    DeviceRegistryBulkResult,
    _normalize_mac,
)
from app.services.audit import log_audit, EventCode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/device-registry", tags=["device-registry"])


def _validate_required_bulk_fields(*, mac: str, nas_ip: Optional[str], name: Optional[str], description: Optional[str], context: str):
    if not mac:
        raise ValueError(f"{context}: missing mac")
    if nas_ip is None or not nas_ip.strip():
        raise ValueError(f"{context}: missing nas_ip")
    if name is None or not name.strip():
        raise ValueError(f"{context}: missing name")
    if description is None or not description.strip():
        raise ValueError(f"{context}: missing description")

    cleaned_ip = nas_ip.strip()
    try:
        ipaddress.ip_address(cleaned_ip)
    except ValueError as exc:
        raise ValueError(f"{context}: invalid nas_ip '{cleaned_ip}'") from exc

    return cleaned_ip, name.strip(), description.strip()


# ÔöÇÔöÇ helpers ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ


async def _get_or_404(db: AsyncSession, device_id: int) -> DeviceRegistry:
    result = await db.execute(select(DeviceRegistry).where(DeviceRegistry.id == device_id))
    device = result.scalars().first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


def _to_out(device: DeviceRegistry) -> DeviceRegistryOut:
    out = DeviceRegistryOut.model_validate(device)
    if device.category:
        out.category_name = device.category.name
    return out


# ÔöÇÔöÇ routes ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ


@router.get("", response_model=list[DeviceRegistryOut])
@limiter.limit("60/minute")
async def list_devices(
    request: Request,
    category_id: Optional[int] = Query(None),
    nas_ip: Optional[str] = Query(None),
    is_active: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    q = select(DeviceRegistry)
    if category_id is not None:
        q = q.where(DeviceRegistry.category_id == category_id)
    if nas_ip is not None:
        q = q.where(DeviceRegistry.nas_ip == nas_ip)
    if is_active is not None:
        q = q.where(DeviceRegistry.is_active == is_active)
    q = q.order_by(DeviceRegistry.id)

    result = await db.execute(q)
    devices = result.scalars().all()

    # Eager load categories
    out = []
    for d in devices:
        await db.refresh(d, ["category"])
        out.append(_to_out(d))
    return out


@router.get("/stats")
@limiter.limit("60/minute")
async def device_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    total = await db.scalar(select(func.count()).select_from(DeviceRegistry))
    active = await db.scalar(
        select(func.count()).select_from(DeviceRegistry).where(DeviceRegistry.is_active == 1)
    )
    return {"total": total, "active": active}


@router.get("/{device_id}", response_model=DeviceRegistryOut)
@limiter.limit("60/minute")
async def get_device(
    request: Request,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    device = await _get_or_404(db, device_id)
    await db.refresh(device, ["category"])
    return _to_out(device)


@router.post("", response_model=DeviceRegistryOut, status_code=201)
@limiter.limit("30/minute")
async def create_device(
    request: Request,
    payload: DeviceRegistryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    if payload.category_id:
        cat = await db.scalar(select(NasCategory).where(NasCategory.id == payload.category_id))
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

    device = DeviceRegistry(**payload.model_dump())
    db.add(device)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=f"MAC '{payload.mac}' already registered")
    await db.refresh(device, ["category"])

    await log_audit(db, current_user.username, "CREATE", "device_registry", payload.mac,
                    new_value=payload.model_dump(), event_code=EventCode.ADMIN_005)
    return _to_out(device)


@router.put("/{device_id}", response_model=DeviceRegistryOut)
@limiter.limit("30/minute")
async def update_device(
    request: Request,
    device_id: int,
    payload: DeviceRegistryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    device = await _get_or_404(db, device_id)

    if payload.category_id is not None:
        cat = await db.scalar(select(NasCategory).where(NasCategory.id == payload.category_id))
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")

    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(device, key, value)

    await db.commit()
    await db.refresh(device, ["category"])

    await log_audit(db, current_user.username, "UPDATE", "device_registry", device.mac,
                    new_value=payload.model_dump(exclude_none=True))
    return _to_out(device)


@router.delete("/{device_id}")
@limiter.limit("30/minute")
async def delete_device(
    request: Request,
    device_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    device = await _get_or_404(db, device_id)
    mac = device.mac
    await db.delete(device)
    await db.commit()
    await log_audit(db, current_user.username, "DELETE", "device_registry", mac)
    return {"ok": True}


@router.post("/bulk", response_model=DeviceRegistryBulkResult, status_code=200)
@limiter.limit("10/minute")
async def bulk_create(
    request: Request,
    payload: DeviceRegistryBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """Upsert multiple devices. Existing MACs are updated, new ones created."""
    created = updated = 0
    errors: list[str] = []

    for item in payload.devices:
        cat_id = item.category_id if item.category_id is not None else payload.category_id
        try:
            nas_ip, name, description = _validate_required_bulk_fields(
                mac=item.mac,
                nas_ip=item.nas_ip,
                name=item.name,
                description=item.description,
                context=f"mac {item.mac}",
            )
            existing = await db.scalar(
                select(DeviceRegistry).where(DeviceRegistry.mac == item.mac)
            )
            if existing:
                existing.category_id = cat_id
                existing.nas_ip = nas_ip
                existing.name = name
                existing.description = description
                existing.is_active = item.is_active
                updated += 1
            else:
                db.add(DeviceRegistry(
                    mac=item.mac,
                    category_id=cat_id,
                    nas_ip=nas_ip,
                    name=name,
                    description=description,
                    is_active=item.is_active,
                ))
                created += 1
        except Exception as exc:
            errors.append(f"{item.mac}: {exc}")

    await db.commit()
    await log_audit(db, current_user.username, "BULK_CREATE", "device_registry", "bulk",
                    new_value={"created": created, "updated": updated, "errors": len(errors)})
    return DeviceRegistryBulkResult(created=created, updated=updated, errors=errors)


@router.post("/bulk/csv", response_model=DeviceRegistryBulkResult, status_code=200)
@limiter.limit("10/minute")
async def bulk_create_csv(
    request: Request,
    file: UploadFile = File(...),
    default_category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Upload CSV with columns: mac, nas_ip, name, description, category_id (optional).
    Upserts all rows. Existing MACs are updated.
    """
    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))

    required_headers = {"mac", "nas_ip", "name", "description"}
    csv_headers = set(reader.fieldnames or [])
    missing_headers = sorted(required_headers - csv_headers)
    if missing_headers:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required header(s): {', '.join(missing_headers)}",
        )

    created = updated = 0
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        raw_mac = (row.get("mac") or "").strip()
        if not raw_mac:
            errors.append(f"row {i}: missing mac")
            continue

        try:
            mac = _normalize_mac(raw_mac)
        except ValueError as exc:
            errors.append(f"row {i} ({raw_mac}): {exc}")
            continue

        raw_cat = (row.get("category_id") or "").strip()
        cat_id = int(raw_cat) if raw_cat.isdigit() else default_category_id
        if cat_id is not None:
            cat = await db.scalar(select(NasCategory).where(NasCategory.id == cat_id))
            if not cat:
                errors.append(f"row {i} ({mac}): category_id {cat_id} not found")
                continue
        nas_ip_raw = (row.get("nas_ip") or "").strip() or None
        name_raw = (row.get("name") or "").strip() or None
        description_raw = (row.get("description") or "").strip() or None

        try:
            nas_ip, name, description = _validate_required_bulk_fields(
                mac=mac,
                nas_ip=nas_ip_raw,
                name=name_raw,
                description=description_raw,
                context=f"row {i}",
            )
        except ValueError as exc:
            errors.append(str(exc))
            continue

        try:
            existing = await db.scalar(select(DeviceRegistry).where(DeviceRegistry.mac == mac))
            if existing:
                existing.category_id = cat_id
                existing.nas_ip = nas_ip
                existing.name = name
                existing.description = description
                updated += 1
            else:
                db.add(DeviceRegistry(mac=mac, category_id=cat_id, nas_ip=nas_ip,
                                      name=name, description=description))
                created += 1
        except Exception as exc:
            errors.append(f"row {i} ({mac}): {exc}")

    await db.commit()
    await log_audit(db, current_user.username, "BULK_CSV", "device_registry", file.filename or "upload",
                    new_value={"created": created, "updated": updated, "errors": len(errors)})
    return DeviceRegistryBulkResult(created=created, updated=updated, errors=errors)


@router.get("/bulk/template")
@limiter.limit("30/minute")
async def download_bulk_template(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Generate a CSV template with columns: mac, name, description, category_id, nas_ip.
    Use this template to bulk-import devices via /bulk/csv.
    """
    headers = ["mac", "name", "description", "category_id", "nas_ip"]
    rows = [
        ["0A:00:3E:45:76:4A", "SM Torre Norte", "Cliente premium - sector norte", "2", "192.168.1.11"],
        ["0A:00:3E:45:76:4B", "SM Torre Sur", "Backhaul secundario", "", "192.168.1.12"],
    ]

    # Fetch categories for reference
    result = await db.execute(select(NasCategory).order_by(NasCategory.name))
    categories = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write data section with comment header
    writer.writerow(["# Device Registry Bulk Import Template"])
    writer.writerow(["# Columns: mac, name, description, category_id, nas_ip"])
    writer.writerow(["# Supported MAC formats: 0A:00:3E:45:76:4A, 0A-00-3E-45-76-4A, 0A00.3E45.764A, 0A003E45764A (case-insensitive)"])
    writer.writerow(["# MAC addresses will be normalized to lowercase 12-char hex (e.g. 0a003e45764a)"])
    writer.writerow(["# Categories available:"] + [f"{c.id}={c.name}" for c in categories])
    writer.writerow([])
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)

    csv_content = output.getvalue()

    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=device_registry_bulk_template.csv"},
    )
