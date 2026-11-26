from datetime import datetime, timedelta
import time
from typing import Optional
import jwt
from jwt.exceptions import InvalidTokenError
import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.session import get_db
from app.models.models import AdminUser
import os

# Configuration
# SECRET_KEY is required — the application will not start without it.
# Set the SECRET_KEY environment variable to a strong random secret.
_secret_key = os.getenv("SECRET_KEY")
if not _secret_key:
    raise RuntimeError(
        "SECRET_KEY environment variable is required. "
        "Set it to a strong random secret before starting the application."
    )
SECRET_KEY: str = _secret_key

# JWT_ALGORITHM is configurable via the ALGORITHM environment variable (default: HS256).
# Supported values: HS256, HS384, HS512 (symmetric) or RS256/RS512 (asymmetric, requires key pair).
ALGORITHM = os.getenv("ALGORITHM", "HS256")
# Idle timeout: each token lives this long; activity refreshes it (#135).
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
SESSION_MAX_HOURS_LIMIT = 24


def parse_session_max_hours(raw: Optional[str]) -> int:
    """Absolute session lifetime in hours (default 12, at most 24)."""
    value = (raw or "").strip()
    if not value.lstrip("-").isdigit():
        return 12
    hours = int(value)
    if not 1 <= hours <= SESSION_MAX_HOURS_LIMIT:
        raise RuntimeError(
            f"SESSION_MAX_HOURS={hours} must be between 1 and {SESSION_MAX_HOURS_LIMIT}."
        )
    return hours


# Absolute lifetime: refresh never extends a session past this (#135).
SESSION_MAX_HOURS = parse_session_max_hours(os.getenv("SESSION_MAX_HOURS"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a bcrypt hash."""
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def get_password_hash(password: str) -> str:
    """Hash a plain password with bcrypt."""
    return _bcrypt.hashpw(
        password.encode("utf-8"),
        _bcrypt.gensalt(),
    ).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def issue_session_token(user: AdminUser, auth_time: Optional[int] = None) -> str:
    """Token for `user`: expires after the idle period, never past the session end.

    `auth_time` (epoch seconds) is when the session started; it is carried over
    unchanged on refresh. Role and force_change come from the DB row.
    """
    now = int(time.time())
    session_start = now if auth_time is None else auth_time
    session_end = session_start + SESSION_MAX_HOURS * 3600
    claims = {
        "sub": user.username,
        "role": user.role,
        "force_change": user.force_password_change == 1,
        "auth_time": session_start,
        "iat": now,  # lets the UI pace refreshes to the token lifetime
        "exp": min(now + ACCESS_TOKEN_EXPIRE_MINUTES * 60, session_end),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub") or ""
        if not username:
            raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    result = await db.execute(select(AdminUser).where(AdminUser.username == username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: AdminUser = Depends(get_current_user)):
    if not bool(current_user.is_active):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
