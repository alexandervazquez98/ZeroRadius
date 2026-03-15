from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.session import get_db
from app.models.models import AdminUser
from app.schemas.schemas import AdminUserCreate, AdminUserOut, AdminUserUpdate
from app.core.security import get_current_active_user, get_password_hash
from app.core.rbac import require_roles, Role
from app.services.audit import log_audit, EventCode
from app.services.lockout import unlock_user

router = APIRouter(prefix="/admin-users", tags=["admin-users"])


@router.get("", response_model=list[AdminUserOut])
async def get_admin_users(
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    result = await db.execute(select(AdminUser))
    return result.scalars().all()


@router.post("", response_model=AdminUserOut)
async def create_admin_user(
    user: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    # Check if user already exists
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == user.username)
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username already registered")

    # Only superadmin can assign the superadmin role
    if user.role == Role.SUPERADMIN.value:
        if getattr(current_user, "role", None) != Role.SUPERADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmin can create accounts with the superadmin role.",
            )

    hashed_password = get_password_hash(user.password)
    db_user = AdminUser(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        is_active=user.is_active,
        role=user.role,
        force_password_change=1,  # Force change on first login
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)

    await log_audit(
        db,
        current_user.username,
        "CREATE",
        "admin_users",
        user.username,
        new_value=user.model_dump(exclude={"password"}),
        event_code=EventCode.ADMIN_001,
    )
    return db_user


@router.put("/{id}", response_model=AdminUserOut)
async def update_admin_user(
    id: int,
    user_update: AdminUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    result = await db.execute(select(AdminUser).where(AdminUser.id == id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    old_data = AdminUserOut.model_validate(db_user).model_dump()

    if user_update.password:
        db_user.hashed_password = get_password_hash(user_update.password)
        db_user.force_password_change = 1

    if user_update.is_active is not None:
        db_user.is_active = user_update.is_active

    if user_update.email is not None:
        db_user.email = user_update.email

    if user_update.role is not None:
        # Only superadmin can assign the superadmin role
        if user_update.role == Role.SUPERADMIN.value:
            if getattr(current_user, "role", None) != Role.SUPERADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only superadmin can assign the superadmin role.",
                )
        db_user.role = user_update.role

    await db.commit()
    await db.refresh(db_user)

    await log_audit(
        db,
        current_user.username,
        "UPDATE",
        "admin_users",
        db_user.username,
        old_value=old_data,
        event_code=EventCode.ADMIN_002,
    )
    return db_user


@router.delete("/{id}")
async def delete_admin_user(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    if id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = await db.execute(select(AdminUser).where(AdminUser.id == id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if db_user.username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete super admin")

    old_data = AdminUserOut.model_validate(db_user).model_dump()
    await db.delete(db_user)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "DELETE",
        "admin_users",
        db_user.username,
        old_value=old_data,
        event_code=EventCode.ADMIN_003,
    )
    return {"ok": True}


@router.post("/{id}/unlock")
async def unlock_admin_user(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = require_roles(Role.SUPERADMIN),
):
    """
    Superadmin endpoint: immediately clears a locked-out user's failed attempts.
    """
    result = await db.execute(select(AdminUser).where(AdminUser.id == id))
    db_user = result.scalars().first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    await unlock_user(db, db_user.username)

    await log_audit(
        db,
        current_user.username,
        f"Unlocked account for {db_user.username}",
        "admin_users",
        db_user.username,
        event_code=EventCode.ADMIN_002,
    )
    return {"ok": True, "message": f"User {db_user.username} has been unlocked."}
