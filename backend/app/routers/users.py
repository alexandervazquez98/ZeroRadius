from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from starlette.requests import Request
from app.db.session import get_db
from app.models.models import RadCheck, RadReply, AdminUser
from app.schemas.schemas import (
    RadCheckCreate,
    RadCheckOut,
    RadReplyCreate,
    RadReplyOut,
    RadCheckUpdate,
)
from app.services.audit import log_audit
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[RadCheckOut])
@limiter.limit("60/minute")
async def get_users(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    limit = min(limit, 100)
    result = await db.execute(select(RadCheck).offset(skip).limit(limit))
    return result.scalars().all()


import hashlib


@router.post("/check", response_model=RadCheckOut)
@limiter.limit("30/minute")
async def create_user_check(
    request: Request,
    user: RadCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    # Hash password if using MD5-Password
    if user.attribute == "MD5-Password":
        user.value = hashlib.md5(user.value.encode()).hexdigest()

    new_user = RadCheck(**user.model_dump())
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "radcheck",
        user.username,
        new_value=user.model_dump(),
    )
    return new_user


@router.put("/check/{id}", response_model=RadCheckOut)
@limiter.limit("30/minute")
async def update_user_check(
    request: Request,
    id: int,
    user_update: RadCheckUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    result = await db.execute(select(RadCheck).where(RadCheck.id == id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User check attribute not found")

    old_data = {
        "username": user.username,
        "attribute": user.attribute,
        "value": user.value,
    }

    update_data = user_update.model_dump(exclude_unset=True)

    # Check if we need to hash the value
    target_attribute = update_data.get("attribute", user.attribute)
    if target_attribute == "MD5-Password" and "value" in update_data:
        # Need to verify if the value is already hashed?
        # Assuming input is always plaintext for updates for simplicity,
        # or we could try to detect length. Ideally frontend sends metadata.
        # For now, always hash if input is provided.
        update_data["value"] = hashlib.md5(update_data["value"].encode()).hexdigest()

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "radcheck",
        user.username,
        old_value=old_data,
        new_value=update_data,
    )
    return user


@router.delete("/check/{id}")
@limiter.limit("30/minute")
async def delete_user_check(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    result = await db.execute(select(RadCheck).where(RadCheck.id == id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User check attribute not found")

    old_data = {
        "username": user.username,
        "attribute": user.attribute,
        "value": user.value,
    }
    await db.delete(user)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "radcheck",
        user.username,
        old_value=old_data,
    )
    return {"ok": True}


@router.post("/reply", response_model=RadReplyOut)
@limiter.limit("30/minute")
async def create_user_reply(
    request: Request,
    reply: RadReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    new_reply = RadReply(**reply.model_dump())
    db.add(new_reply)
    await db.commit()
    await db.refresh(new_reply)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "radreply",
        reply.username,
        new_value=reply.model_dump(),
    )
    return new_reply


@router.delete("/reply/{id}")
@limiter.limit("30/minute")
async def delete_user_reply(
    request: Request,
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(RadReply).where(RadReply.id == id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Attribute not found")

    old_data = {
        "username": item.username,
        "attribute": item.attribute,
        "value": item.value,
    }
    await db.delete(item)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "radreply",
        item.username,
        old_value=old_data,
    )
    return {"ok": True}
