"""
LockoutService — ISO 27001 A.5.17
Account lockout based on failed login attempts stored in login_attempts table.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

logger = logging.getLogger(__name__)

# Lockout constants
LOCKOUT_ATTEMPTS = 5  # Max failed attempts before lockout
LOCKOUT_WINDOW_MINUTES = 10  # Window to count failed attempts
LOCKOUT_DURATION_MINUTES = 15  # How long the account stays locked
CLEANUP_AGE_HOURS = 24  # Delete attempts older than this
RECENT_SESSION_MINUTES = 30  # Window to consider a session as active (smart lockout)


async def has_recent_session(db: AsyncSession, username: str) -> bool:
    """
    Check if the user had a successful login in the last RECENT_SESSION_MINUTES.
    Returns True if a recent successful session exists (smart lockout bypass).
    """
    from app.models.models import LoginAttempt

    session_window = datetime.utcnow() - timedelta(minutes=RECENT_SESSION_MINUTES)

    result = await db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.username == username,
            LoginAttempt.success == 1,
            LoginAttempt.attempted_at >= session_window,
        )
    )
    return (result.scalar() or 0) > 0


async def check_lockout(db: AsyncSession, username: str) -> bool:
    """
    Check if a username is currently locked out.
    Returns True if locked, False if allowed to attempt login.

    Smart lockout: if the user has a successful login in the last
    RECENT_SESSION_MINUTES, bypass lockout entirely — protects active admins
    from being blocked by brute-force attacks from other IPs.
    """
    from app.models.models import LoginAttempt

    # Smart lockout: bypass if user has an active recent session
    if await has_recent_session(db, username):
        return False

    window_start = datetime.utcnow() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)

    result = await db.execute(
        select(func.count(LoginAttempt.id)).where(
            LoginAttempt.username == username,
            LoginAttempt.success == 0,
            LoginAttempt.attempted_at >= window_start,
        )
    )
    failed_count = result.scalar() or 0
    return failed_count >= LOCKOUT_ATTEMPTS


async def record_attempt(
    db: AsyncSession, username: str, ip_address: Optional[str], success: bool
) -> None:
    """
    Record a login attempt (success or failure) in the login_attempts table.
    Also cleans up old records (older than CLEANUP_AGE_HOURS).
    """
    from app.models.models import LoginAttempt

    # Record the attempt
    attempt = LoginAttempt(
        username=username,
        ip_address=ip_address,
        attempted_at=datetime.utcnow(),
        success=1 if success else 0,
    )
    db.add(attempt)

    # Clean up old attempts (older than 24h) to prevent table bloat
    cutoff = datetime.utcnow() - timedelta(hours=CLEANUP_AGE_HOURS)
    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.username == username,
            LoginAttempt.attempted_at < cutoff,
        )
    )

    await db.commit()


async def unlock_user(db: AsyncSession, username: str) -> None:
    """
    Superadmin unlock: delete all recent failed attempts for a username,
    effectively clearing the lockout immediately.
    """
    from app.models.models import LoginAttempt

    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.username == username,
            LoginAttempt.success == 0,
        )
    )
    await db.commit()
    logger.info("LockoutService: manually unlocked user '%s'", username)
