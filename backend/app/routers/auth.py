import re
import bcrypt as _bcrypt
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import (
    verify_password,
    create_access_token,
    get_password_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_active_user,
)
from app.models.models import AdminUser
from app.schemas.schemas import Token
from app.services.lockout import (
    check_lockout,
    record_attempt,
    LOCKOUT_DURATION_MINUTES,
)
from app.services.audit import log_audit, EventCode
from app.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

# Static dummy bcrypt hash for timing oracle mitigation.
# Generated once at module load so every failed login uses the SAME hash,
# ensuring consistent bcrypt verification timing regardless of username.
_DUMMY_HASH = _bcrypt.hashpw(b"dummy_password_for_timing", _bcrypt.gensalt())


def _validate_password_strength(password: str) -> None:
    """Validate password meets complexity requirements."""
    if len(password) < 12:
        raise HTTPException(
            status_code=422, detail="Password must be at least 12 characters long"
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=422,
            detail="Password must contain at least one uppercase letter",
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=422, detail="Password must contain at least one digit"
        )
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]", password):
        raise HTTPException(
            status_code=422,
            detail="Password must contain at least one special character",
        )


@router.post("/token", response_model=Token)
@limiter.limit("5/minute")
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Authenticate admin user and return JWT.

    NOTE: Initial admin seeding is manual — run ``python scripts/seed_admin.py``
    to create the first admin account. No automatic provisioning occurs here.
    """
    # Extract client IP for audit
    client_ip: str | None = request.client.host if request.client else None

    # --- Check lockout BEFORE verifying password ---
    if await check_lockout(db, form_data.username):
        await log_audit(
            db,
            form_data.username,
            "LOGIN_FAILED",
            "auth",
            form_data.username,
            new_value={"reason": "account_locked"},
            event_code=EventCode.ADMIN_007,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Account temporarily locked due to {LOCKOUT_DURATION_MINUTES} minutes "
                "of repeated failed attempts. Try again later or ask an administrator to unlock."
            ),
        )

    # Fetch user
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == form_data.username)
    )
    user = result.scalars().first()

    if not user:
        await record_attempt(db, form_data.username, client_ip, success=False)
        await log_audit(
            db,
            form_data.username,
            "LOGIN_FAILED",
            "auth",
            form_data.username,
            new_value={"reason": "user_not_found"},
            event_code=EventCode.ADMIN_007,
        )
        # Timing oracle mitigation: dummy bcrypt with static hash
        _bcrypt.checkpw(b"dummy_password_for_timing", _DUMMY_HASH)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        await record_attempt(db, form_data.username, client_ip, success=False)
        await log_audit(
            db,
            form_data.username,
            "LOGIN_FAILED",
            "auth",
            form_data.username,
            new_value={"reason": "wrong_password"},
            event_code=EventCode.ADMIN_007,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Successful login
    await record_attempt(db, form_data.username, client_ip, success=True)

    # Log ADMIN-007 audit event
    await log_audit(
        db,
        admin_user=user.username,
        action="Login",
        table_affected="admin_users",
        target_user=user.username,
        event_code=EventCode.ADMIN_007,
    )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Include 'role' and 'force_change' in JWT payload
    access_token = create_access_token(
        data={
            "sub": user.username,
            "role": user.role,
            "force_change": user.force_password_change == 1,
        },
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


from pydantic import BaseModel


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


@router.post("/change-password")
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    pwd: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_active_user),
):
    if not verify_password(pwd.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Invalid old password")

    _validate_password_strength(pwd.new_password)

    current_user.hashed_password = get_password_hash(pwd.new_password)
    current_user.force_password_change = 0  # Reset flag

    db.add(current_user)
    await db.commit()

    await log_audit(
        db,
        current_user.username,
        "PASSWORD_CHANGED",
        "auth",
        current_user.username,
    )

    return {"message": "Password updated successfully"}
