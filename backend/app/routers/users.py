import secrets

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
    PasswordResetRequest,
    PasswordResetOut,
    SETTABLE_PASSWORD_TYPES,
    settable_password_type,
    SetupLinkRequest,
    SetupLinkOut,
    SetupLinkStatus,
)
from app.services import password_setup
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


# Roles that may create RADIUS users and add/remove their reply attributes.
# readonly and auditor are read-only roles. Editing or deleting a password row
# stays limited to admin/superadmin (see update/delete below).
_RADIUS_USER_WRITERS = require_roles(Role.SUPERADMIN, Role.ADMIN, Role.HELPDESK)


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
    rows = result.scalars().all()

    # Attach the latest self-service setup link status (#101 C).
    links = await password_setup.latest_links(db, [r.id for r in rows])
    now = password_setup.utcnow()
    out = []
    for row in rows:
        item = RadCheckOut.model_validate(row)
        link = links.get(row.id)
        if link is not None:
            item.setup_link = SetupLinkStatus(
                status=password_setup.link_status(link, now),
                created_by=link.created_by,
                created_at=link.created_at,
                expires_at=link.expires_at,
                used_at=link.used_at,
            )
        out.append(item)
    return out


@router.post("/check", response_model=RadCheckOut)
@limiter.limit("30/minute")
async def create_user_check(
    request: Request,
    user: RadCheckCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = _RADIUS_USER_WRITERS,
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
            is_password_attribute(target_attribute)
            and "value" in update_data
            and settable_password_type(target_attribute) is None
        ):
            raise HTTPException(
                status_code=422,
                detail=f"Passwords can only be set as: {', '.join(SETTABLE_PASSWORD_TYPES)}",
            )
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

    # A pending self-service link must not outlive an admin edit of the
    # credential or its owner: it would overwrite the new state when used.
    if any(update_data.get(k, getattr(user, k)) != getattr(user, k) for k in ("username", "attribute")) or (
        "value" in update_data
    ):
        await password_setup.revoke_active_links(db, user.id)

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


@router.post("/check/{id}/reset-password", response_model=PasswordResetOut)
@limiter.limit("30/minute")
async def reset_user_password(
    request: Request,
    id: int,
    body: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """Set a new password for a password row (#101 B).

    Either ``password`` or ``generate=true``. A generated password is
    returned once in the response and never stored or logged in cleartext
    (unless the row uses Cleartext-Password).
    """
    if (body.password is None) == (not body.generate):
        raise HTTPException(
            status_code=422, detail="Provide either a password or generate=true"
        )
    if body.password == "":
        raise HTTPException(status_code=422, detail="Password cannot be empty")

    result = await db.execute(select(RadCheck).where(RadCheck.id == id))
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="User check attribute not found")
    if not is_password_attribute(row.attribute):
        raise HTTPException(status_code=422, detail="This attribute is not a password")

    # Default to the row's current type, but only types the backend can hash.
    requested = body.password_type if body.password_type is not None else row.attribute
    attribute = settable_password_type(requested)
    if attribute is None:
        raise HTTPException(
            status_code=422,
            detail=f"password_type must be one of: {', '.join(SETTABLE_PASSWORD_TYPES)}"
            + ("" if body.password_type is not None else f" (current type {row.attribute} cannot be set)"),
        )

    generated = secrets.token_urlsafe(15) if body.generate else None
    plaintext = generated or body.password

    old_attribute = row.attribute
    row.attribute = attribute
    row.value = hash_password_value(attribute, plaintext)
    # An admin-set password supersedes any pending self-service link.
    await password_setup.revoke_active_links(db, row.id)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "PASSWORD_RESET",
        "radcheck",
        row.username,
        old_value={"attribute": old_attribute},
        new_value={"attribute": attribute, "generated": body.generate},
    )
    return PasswordResetOut(
        id=row.id, username=row.username, attribute=attribute, generated_password=generated
    )


@router.post("/check/{id}/setup-link", response_model=SetupLinkOut)
@limiter.limit("30/minute")
async def create_setup_link(
    request: Request,
    id: int,
    body: SetupLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.ADMIN, Role.SUPERADMIN),
):
    """Generate a one-time, 72h self-service password setup link (#101 C).

    The current password is blocked immediately; the user regains access by
    setting a new password through the link. The token is returned once and
    only its hash is stored; a previous pending link for the row is revoked.
    """
    result = await db.execute(select(RadCheck).where(RadCheck.id == id))
    row = result.scalars().first()
    if not row:
        raise HTTPException(status_code=404, detail="User check attribute not found")
    if not is_password_attribute(row.attribute):
        raise HTTPException(status_code=422, detail="This attribute is not a password")

    requested = body.password_type if body.password_type is not None else row.attribute
    attribute = settable_password_type(requested)
    if attribute is None:
        raise HTTPException(
            status_code=422,
            detail=f"password_type must be one of: {', '.join(SETTABLE_PASSWORD_TYPES)}"
            + ("" if body.password_type is not None else f" (current type {row.attribute} cannot be set)"),
        )

    old_attribute = row.attribute
    token, link = await password_setup.create_link(db, row, attribute, current_user.username)

    await log_audit(
        db,
        current_user.username,
        "PASSWORD_SETUP_LINK_CREATED",
        "radcheck",
        row.username,
        old_value={"attribute": old_attribute},
        new_value={"attribute": attribute, "expires_at": link.expires_at.isoformat()},
    )
    return SetupLinkOut(
        id=row.id, username=row.username, attribute=attribute, token=token, expires_at=link.expires_at
    )


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
    await password_setup.delete_links(db, id)
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
    current_user: AdminUser = _RADIUS_USER_WRITERS,
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
    current_user: AdminUser = _RADIUS_USER_WRITERS,
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
