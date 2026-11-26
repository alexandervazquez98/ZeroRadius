import re
import time
import bcrypt as _bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.core.security import (
    ALGORITHM,
    SECRET_KEY,
    SESSION_MAX_HOURS,
    issue_session_token,
    oauth2_scheme,
    verify_password,
    get_password_hash,
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

    access_token = issue_session_token(user)
    return {"access_token": access_token, "token_type": "bearer"}


SESSION_EXPIRED = "Session expired. Please sign in again."


@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")
async def refresh_session(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Issue a fresh token for an active session (sliding idle timeout, #135).

    The current token must still be valid. The new token keeps the session
    start (`auth_time`) and never outlives SESSION_MAX_HOURS. The admin is
    re-read from the DB: disabled or deleted admins get 401, and role /
    force_change changes apply immediately.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        raise unauthorized

    auth_time = payload.get("auth_time")
    if not isinstance(auth_time, int) or time.time() >= auth_time + SESSION_MAX_HOURS * 3600:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=SESSION_EXPIRED,
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(AdminUser).where(AdminUser.username == payload.get("sub")))
    user = result.scalars().first()
    if user is None or not bool(user.is_active):
        raise unauthorized

    return {"access_token": issue_session_token(user, auth_time=auth_time), "token_type": "bearer"}


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
