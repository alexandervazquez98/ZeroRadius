from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from starlette.requests import Request
from datetime import datetime, timedelta
from app.db.session import get_db
from app.models.models import RadCheck, RadReply, AdminUser
from app.schemas.schemas import (
    RadCheckCreate,
    RadCheckOut,
    RadReplyCreate,
    RadReplyOut,
    RadCheckUpdate,
    is_password_attribute,
)
from app.services.audit import log_audit
from app.core.radius_passwords import hash_password_value
from app.core.security import get_current_active_user
from app.core.rbac import require_roles, Role
from app.core.limiter import limiter

router = APIRouter(prefix="/users", tags=["users"])

REDACTED = "***"


def _audit_safe(data: dict, attribute: str) -> dict:
    """Copy of an audit payload with the password value redacted (#101)."""
    if "value" in data and is_password_attribute(attribute):
        return {**data, "value": REDACTED}
    return data


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


@router.post("/check", response_model=RadCheckOut)
@limiter.limit("30/minute")
async def create_user_check(
    request: Request,
    user: RadCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    # Input is the plaintext password; store it in the attribute's format
    # (MD5-Password / NT-Password are hashed).
    user.value = hash_password_value(user.attribute, user.value)

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
        new_value=_audit_safe(user.model_dump(), user.attribute),
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
    if update_data.get("value") is None:
        update_data.pop("value", None)

    # Password values are write-only (#101) and a stored hash cannot be
    # converted to another format (#95): omitting "value" keeps the current
    # password, and changing the attribute of a password row (or turning a
    # row into one) requires a new value, so a stored credential never
    # becomes a readable value of another attribute.
    target_attribute = update_data.get("attribute", user.attribute)
    involves_password = is_password_attribute(target_attribute) or is_password_attribute(
        user.attribute
    )
    if involves_password:
        if is_password_attribute(target_attribute) and update_data.get("value") == "":
            raise HTTPException(status_code=422, detail="Password cannot be empty")
        if (
            target_attribute.casefold() != user.attribute.casefold()
            and "value" not in update_data
        ):
            raise HTTPException(
                status_code=422,
                detail="Changing the password type requires a new password",
            )
    if "value" in update_data:
        # Input is always the plaintext password; hash it like create does.
        update_data["value"] = hash_password_value(target_attribute, update_data["value"])

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
        old_value=_audit_safe(old_data, old_data["attribute"]),
        new_value=_audit_safe(update_data, target_attribute),
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
        old_value=_audit_safe(old_data, old_data["attribute"]),
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


# --- JIT Break-Glass Access ---
@router.post("/jit-requests/{username}/approve")
@limiter.limit("5/minute")
async def approve_jit_access(
    username: str,
    request: Request,
    ttl_hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN, Role.ADMIN),
):
    """
    Authorizes temporary elevation of a user by injecting the Expiration attribute
    into their radcheck table.
    """
    expiration_date = datetime.now() + timedelta(hours=ttl_hours)
    expiration_str = expiration_date.strftime("%d %b %Y %H:%M")

    # Check if Expiration attribute already exists for this user
    stmt = select(RadCheck).where(
        RadCheck.username == username, RadCheck.attribute == "Expiration"
    )
    existing_attr = (await db.execute(stmt)).scalars().first()

    if existing_attr:
        existing_attr.value = expiration_str
        existing_attr.op = ":="
    else:
        new_attr = RadCheck(
            username=username, attribute="Expiration", op=":=", value=expiration_str
        )
        db.add(new_attr)

    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "JIT_APPROVED",
        "radcheck",
        username,
        new_value={"ttl_hours": ttl_hours, "expiration": expiration_str},
    )

    return {"message": f"JIT Access approved. Calculated expiration: {expiration_str}"}
