"""
NAS router — nas-categories update (T2.3)
Adds category_id pass-through on create/update and category_name resolution on reads.
"""

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.responses import Response
from app.db.session import get_db
from app.models.models import Nas, NasCategory, AdminUser, AccessPolicyAssignment
from app.schemas.schemas import NasCreate, NasOut, NasBulkResult, NasBulkRowError
from app.services.audit import log_audit, EventCode
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nas", tags=["nas"])


# NAS changes need no RADIUS restart: FreeRADIUS looks each NAS up in the nas
# table on its first packet and caches it for RADIUS_CLIENT_LIFETIME seconds
# (radius/sites/dynamic-clients).


def _nas_to_out(nas: Nas) -> NasOut:
    """Serialize Nas ORM → NasOut, resolving category_name from the loaded relationship."""
    return NasOut(
        id=nas.id,
        nasname=nas.nasname,
        shortname=nas.shortname,
        type=nas.type,
        ports=nas.ports,
        secret=nas.secret,
        server=nas.server,
        community=nas.community,
        description=nas.description,
        category_id=nas.category_id,
        category_name=nas.category.name if nas.category else None,
    )


@router.get("", response_model=list[NasOut])
@limiter.limit("60/minute")
async def get_nas(
    request: Request,
    category_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    query = select(Nas).options(selectinload(Nas.category))
    if category_id is not None:
        if category_id <= 0:
            raise HTTPException(status_code=422, detail="category_id must be positive")
        query = query.where(Nas.category_id == category_id)
    query = query.order_by(Nas.id)
    result = await db.execute(query)
    return [_nas_to_out(n) for n in result.scalars().all()]


@router.post("", response_model=NasOut)
@limiter.limit("10/minute")
async def create_nas(
    request: Request,
    nas: NasCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    new_nas = Nas(**nas.model_dump())
    db.add(new_nas)
    await db.commit()
    await db.refresh(new_nas)

    # Reload relationship for the response
    result = await db.execute(
        select(Nas).options(selectinload(Nas.category)).where(Nas.id == new_nas.id)
    )
    new_nas = result.scalars().first()

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "nas",
        nas.nasname,
        new_value=nas.model_dump(exclude={"secret"}),
        event_code=EventCode.ADMIN_005,
    )
    return _nas_to_out(new_nas)


# ── Bulk import (CSV) ─────────────────────────────────────────────────────────

BULK_MAX_BYTES = 1024 * 1024
BULK_MAX_ROWS = 5000
BULK_COLUMNS = ["nasname", "shortname", "secret", "category", "type", "description"]
BULK_REQUIRED = {"nasname", "secret"}
# DB column widths not covered by NasCreate. An oversize value would make the
# single commit fail for the whole file, so it is reported as a row error.
_BULK_MAX_LEN = {"nasname": 128, "shortname": 32, "secret": 60, "type": 30, "description": 200}
_BULK_UPDATABLE = ("shortname", "description", "type", "category_id")


def _validation_message(exc: ValidationError) -> str:
    """Field + message only: pydantic's str(exc) echoes the input (the secret)."""
    parts = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", ())) or "row"
        msg = str(err.get("msg", "invalid value")).removeprefix("Value error, ")
        parts.append(f"{field}: {msg}")
    return "; ".join(parts)


async def _existing_by_nasname(db: AsyncSession, nasnames: list[str]) -> dict[str, list[Nas]]:
    found: dict[str, list[Nas]] = {}
    for start in range(0, len(nasnames), 500):
        chunk = nasnames[start:start + 500]
        result = await db.execute(select(Nas).where(Nas.nasname.in_(chunk)))
        for nas in result.scalars().all():
            found.setdefault(nas.nasname, []).append(nas)
    return found


def _header(name) -> str:
    """Header names ignore surrounding spaces and case (Excel writes 'Category')."""
    return (name or "").strip().lower()


def _delimiter(text: str) -> str:
    """Excel with a Spanish/European locale saves CSV with ';' instead of ','.

    The header line decides: ';' only when it has semicolons and no commas,
    so comma files (including commas inside descriptions) parse as before.
    """
    header_line = text.split("\n", 1)[0]
    return ";" if ";" in header_line and "," not in header_line else ","


def _clean_row(raw: dict) -> dict[str, str]:
    return {
        _header(key): value.strip() if isinstance(value, str) else ""
        for key, value in raw.items()
    }


@router.post("/bulk/csv", response_model=NasBulkResult)
@limiter.limit("10/minute")
async def bulk_import_nas_csv(
    request: Request,
    file: UploadFile = File(...),
    default_category_id: Optional[int] = Query(None),
    dry_run: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    """Create or update NAS clients from a CSV file.

    Columns: nasname, shortname, secret, category (name), type, description.
    Separated by ',' or ';' (Excel with a Spanish locale), decided by the header.
    A nasname matching exactly one existing row updates it; rows with errors
    are skipped and reported. FreeRADIUS is not restarted.
    """
    content = await file.read(BULK_MAX_BYTES + 1)
    if len(content) > BULK_MAX_BYTES:
        raise HTTPException(status_code=413, detail="CSV file exceeds 1 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV file must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text), delimiter=_delimiter(text))
    headers = {_header(h) for h in (reader.fieldnames or [])}
    missing = sorted(BULK_REQUIRED - headers)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"CSV missing required header(s): {', '.join(missing)}",
        )
    # (data row number, cleaned row). Rows whose cells are all empty (",,,,,"
    # from spreadsheets) are skipped but still counted, so row numbers in
    # errors match the file.
    numbered: list[tuple[int, dict[str, str]]] = []
    for number, raw in enumerate(reader, start=1):
        if number > BULK_MAX_ROWS:
            raise HTTPException(status_code=422, detail=f"CSV exceeds {BULK_MAX_ROWS} data rows")
        row = _clean_row(raw)
        if any(row.values()):
            numbered.append((number, row))
    rows = [row for _, row in numbered]

    if default_category_id is not None and (
        default_category_id <= 0 or await db.get(NasCategory, default_category_id) is None
    ):
        raise HTTPException(status_code=422, detail="default_category_id not found")

    categories = {
        c.name.lower(): c.id for c in (await db.execute(select(NasCategory))).scalars().all()
    }
    existing = await _existing_by_nasname(
        db, sorted({r["nasname"] for r in rows if r.get("nasname")})
    )

    created = updated = 0
    errors: list[NasBulkRowError] = []
    seen: set[str] = set()

    for number, row in numbered:
        nasname = row.get("nasname") or None

        def fail(message: str) -> None:
            errors.append(NasBulkRowError(row=number, nasname=nasname, error=message))

        if nasname is None:
            fail("nasname is required")
            continue
        if nasname in seen:
            fail("duplicate nasname in file")
            continue
        seen.add(nasname)
        if not row.get("secret"):
            fail("secret is required")
            continue
        too_long = [f for f, limit in _BULK_MAX_LEN.items() if len(row.get(f, "")) > limit]
        if too_long:
            fail("; ".join(f"{f}: must be at most {_BULK_MAX_LEN[f]} characters" for f in too_long))
            continue

        category_name = row.get("category", "")
        if category_name:
            category_id = categories.get(category_name.lower())
            if category_id is None:
                fail(f"unknown category '{category_name}'")
                continue
        else:
            category_id = default_category_id

        fields = {
            "nasname": nasname,
            "secret": row["secret"],
            "shortname": row.get("shortname") or None,
            "description": row.get("description") or None,
            "category_id": category_id,
        }
        if row.get("type"):
            fields["type"] = row["type"]
        try:
            validated = NasCreate(**fields)
        except ValidationError as exc:
            fail(_validation_message(exc))
            continue

        matches = existing.get(nasname, [])
        if len(matches) > 1:
            fail(f"nasname matches multiple existing NAS rows ({len(matches)}); edit them individually")
            continue
        if matches:
            if not dry_run:
                target = matches[0]
                target.secret = validated.secret
                # Empty optional cells keep the existing value.
                for key in _BULK_UPDATABLE:
                    value = fields.get(key)
                    if value is not None:
                        setattr(target, key, value)
            updated += 1
        else:
            if not dry_run:
                db.add(Nas(**validated.model_dump()))
            created += 1

    if not dry_run:
        await log_audit(
            db,
            current_user.username,
            "BULK_CSV",
            "nas",
            file.filename or "upload",
            new_value={"created": created, "updated": updated, "errors": len(errors)},
            commit=False,
        )
        await db.commit()

    logger.info(
        "NAS bulk CSV by %s: created=%d updated=%d errors=%d dry_run=%s",
        current_user.username, created, updated, len(errors), dry_run,
    )
    return NasBulkResult(created=created, updated=updated, errors=errors, dry_run=dry_run)


@router.get("/bulk/template")
@limiter.limit("30/minute")
async def download_nas_bulk_template(
    request: Request,
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=BULK_COLUMNS)
    writer.writeheader()
    writer.writerow({
        "nasname": "192.0.2.10",
        "shortname": "AP-BRANCH1-01",
        "secret": "EXAMPLE-ONLY-replace-this-shared-secret-0001",
        "category": "AP",
        "type": "other",
        "description": "Branch 1 access point",
    })
    writer.writerow({
        "nasname": "198.51.100.0/24",
        "shortname": "AP-BRANCH2-NET",
        "secret": "EXAMPLE-ONLY-replace-this-shared-secret-0002",
        "category": "",
        "type": "",
        "description": "Branch 2 AP subnet (uses default_category_id)",
    })
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=nas_bulk_template.csv"},
    )


@router.put("/{id}", response_model=NasOut)
@limiter.limit("10/minute")
async def update_nas(
    request: Request,
    id: int,
    nas_update: NasCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(
        select(Nas).options(selectinload(Nas.category)).where(Nas.id == id)
    )
    nas = result.scalars().first()
    if not nas:
        raise HTTPException(status_code=404, detail="NAS not found")

    old_data = _nas_to_out(nas).model_dump()
    old_nasname = nas.nasname
    update_data = nas_update.model_dump(exclude_unset=True)

    # Check if secret is being changed → log ADMIN-009
    secret_changed = "secret" in update_data and update_data["secret"] != nas.secret
    nasname_changed = "nasname" in update_data and update_data["nasname"] != old_nasname

    for key, value in update_data.items():
        setattr(nas, key, value)

    if nasname_changed:
        assignments_result = await db.execute(
            select(AccessPolicyAssignment).where(
                AccessPolicyAssignment.nas_ip == old_nasname
            )
        )
        for assignment in assignments_result.scalars().all():
            assignment.nas_ip = update_data["nasname"]

    await db.commit()

    # Reload with category relationship
    result = await db.execute(
        select(Nas).options(selectinload(Nas.category)).where(Nas.id == id)
    )
    nas = result.scalars().first()

    if secret_changed:
        await log_audit(
            db,
            current_user.username,
            "NAS secret changed",
            "nas",
            nas.nasname,
            event_code=EventCode.ADMIN_009,
        )

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "nas",
        nas.nasname,
        old_value={k: v for k, v in old_data.items() if k != "secret"},
        new_value={k: v for k, v in update_data.items() if k != "secret"},
    )
    return _nas_to_out(nas)


@router.delete("/{id}")
@limiter.limit("10/minute")
async def delete_nas(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    result = await db.execute(
        select(Nas).options(selectinload(Nas.category)).where(Nas.id == id)
    )
    nas = result.scalars().first()
    if not nas:
        raise HTTPException(status_code=404, detail="NAS not found")

    old_data = _nas_to_out(nas).model_dump()
    await db.delete(nas)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "nas",
        nas.nasname,
        old_value={k: v for k, v in old_data.items() if k != "secret"},
    )
    return {"ok": True}


@router.get("/ca-certificate")
@limiter.limit("60/minute")
async def get_ca_certificate(
    request: Request,
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Download the RADIUS server CA certificate for client configuration."""
    try:
        import os

        # Try multiple locations for the CA certificate
        cert_paths = [
            "/app/radius-certs/ca.pem",  # Mounted from docker-compose
            "/tmp/radius-ca.pem",  # Legacy path
            "/tmp/ca.pem",  # Legacy path
        ]

        ca_cert = None
        for cert_path in cert_paths:
            if os.path.exists(cert_path):
                with open(cert_path, "r") as f:
                    ca_cert = f.read()
                break

        if not ca_cert:
            raise HTTPException(status_code=404, detail="CA certificate not found")

        # Return as plain text - the frontend will handle the download
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(
            ca_cert,
            media_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": "attachment; filename=radius-ca.pem"},
        )
    except Exception as exc:
        logger.error("Error getting CA certificate: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get CA certificate")
