"""
NasCategories router — nas-categories feature
CRUD for NAS device categories with RBAC and 409 protection on delete-if-in-use.
ISO 27001 A.8.1 — Asset inventory and classification.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import NasCategory, Nas, AdminUser
from app.schemas.schemas import NasCategoryCreate, NasCategoryOut
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.services.audit import log_audit, EventCode
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nas-categories", tags=["nas-categories"])


@router.get("", response_model=list[NasCategoryOut])
async def list_nas_categories(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """List all NAS categories. Accessible by any authenticated user."""
    result = await db.execute(select(NasCategory).order_by(NasCategory.name))
    return result.scalars().all()


@router.get("/{id}", response_model=NasCategoryOut)
async def get_nas_category(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    """Get a single NAS category by ID."""
    result = await db.execute(select(NasCategory).where(NasCategory.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="NAS category not found")
    return category


@router.post("", response_model=NasCategoryOut, status_code=201)
async def create_nas_category(
    payload: NasCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Create a new NAS category.
    Requires admin or superadmin role.
    """
    # Check uniqueness (name)
    existing = await db.execute(
        select(NasCategory).where(NasCategory.name == payload.name)
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=f"A NAS category named '{payload.name}' already exists",
        )

    category = NasCategory(**payload.model_dump(mode="json"))
    db.add(category)
    await db.commit()
    await db.refresh(category)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "nas_categories",
        payload.name,
        new_value=payload.model_dump(mode="json"),
        event_code=EventCode.ADMIN_005,
    )
    return category


@router.put("/{id}", response_model=NasCategoryOut)
async def update_nas_category(
    id: int,
    payload: NasCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """
    Update an existing NAS category.
    Requires admin or superadmin role.
    """
    result = await db.execute(select(NasCategory).where(NasCategory.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="NAS category not found")

    old_data = NasCategoryOut.model_validate(category).model_dump(mode="json")

    # Check name uniqueness (excluding self)
    if payload.name != category.name:
        dup = await db.execute(
            select(NasCategory).where(NasCategory.name == payload.name)
        )
        if dup.scalars().first():
            raise HTTPException(
                status_code=409,
                detail=f"A NAS category named '{payload.name}' already exists",
            )

    for key, value in payload.model_dump(mode="json").items():
        setattr(category, key, value)

    await db.commit()
    await db.refresh(category)

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "nas_categories",
        category.name,
        old_value=old_data,
        new_value=payload.model_dump(mode="json"),
    )
    return category


@router.delete("/{id}")
async def delete_nas_category(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    """
    Delete a NAS category.
    Returns 409 if any NAS devices are assigned to this category.
    Requires superadmin role.
    """
    result = await db.execute(select(NasCategory).where(NasCategory.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="NAS category not found")

    # REQ-01: 409 if any NAS still references this category
    in_use = await db.execute(
        select(Nas).where(Nas.category_id == id)
    )
    if in_use.scalars().first():
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete category '{category.name}': "
                "one or more NAS devices are assigned to it. "
                "Reassign or remove them first."
            ),
        )

    old_data = NasCategoryOut.model_validate(category).model_dump(mode="json")
    await db.delete(category)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "nas_categories",
        category.name,
        old_value=old_data,
    )
    return {"ok": True}
