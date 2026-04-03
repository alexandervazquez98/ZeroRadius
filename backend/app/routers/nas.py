"""
NAS router — nas-categories update (T2.3)
Adds category_id pass-through on create/update and category_name resolution on reads.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.models import Nas, AdminUser
from app.schemas.schemas import NasCreate, NasOut
from app.services.audit import log_audit, EventCode
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
import logging
import docker as docker_sdk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nas", tags=["nas"])


def _reload_radius() -> None:
    """Restart the radius-server container so it re-reads the nas table.

    FreeRADIUS 3.x does not support SIGHUP for client reloading — a full
    container restart is the only way to pick up changes to the nas table.
    The failure is logged as a warning and does NOT abort the API response.
    """
    try:
        client = docker_sdk.from_env()
        container = client.containers.get("radius-server")
        container.restart(timeout=5)
        logger.info("radius-server restarted to reload NAS clients")
    except Exception as exc:
        logger.warning("Could not restart radius-server: %s", exc)


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
        zone_id=nas.zone_id,
        category_id=nas.category_id,
        category_name=nas.category.name if nas.category else None,
    )


@router.get("", response_model=list[NasOut])
async def get_nas(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(Nas).options(selectinload(Nas.category)))
    return [_nas_to_out(n) for n in result.scalars().all()]


@router.post("", response_model=NasOut)
async def create_nas(
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
    _reload_radius()
    return _nas_to_out(new_nas)


@router.put("/{id}", response_model=NasOut)
async def update_nas(
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
    update_data = nas_update.model_dump(exclude_unset=True)

    # Check if secret is being changed → log ADMIN-009
    secret_changed = "secret" in update_data and update_data["secret"] != nas.secret

    for key, value in update_data.items():
        setattr(nas, key, value)

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
    _reload_radius()
    return _nas_to_out(nas)


@router.delete("/{id}")
async def delete_nas(
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
    _reload_radius()
    return {"ok": True}


@router.get("/ca-certificate")
async def get_ca_certificate(
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
