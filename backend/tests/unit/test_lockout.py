"""
T38 — Unit tests for LockoutService.

Uses an in-memory SQLite test_db fixture (from conftest.py).

Tests cover:
- No attempts → not locked
- 4 failed attempts → not locked
- 5 failed attempts → locked
- Expired lockout (attempts older than LOCKOUT_WINDOW_MINUTES) → not locked
- Successful attempt does not contribute to lockout
- Different users are independent
- Smart lockout: user with recent session bypasses lockout (regression)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lockout import (
    check_lockout,
    has_recent_session,
    record_attempt,
    unlock_user,
    LOCKOUT_ATTEMPTS,
    LOCKOUT_WINDOW_MINUTES,
    LOCKOUT_DURATION_MINUTES,
    RECENT_SESSION_MINUTES,
)


class TestCheckLockout:
    async def test_no_attempts_not_locked(self, test_db: AsyncSession):
        """With no prior attempts the account is not locked."""
        result = await check_lockout(test_db, "brandnew_user")
        assert result is False

    async def test_four_fails_not_locked(self, test_db: AsyncSession):
        """4 failed attempts is below the threshold — not locked."""
        for _ in range(4):
            await record_attempt(test_db, "user_four_fails", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "user_four_fails") is False

    async def test_five_fails_triggers_lockout(self, test_db: AsyncSession):
        """Exactly 5 failed attempts → account is locked."""
        for _ in range(LOCKOUT_ATTEMPTS):
            await record_attempt(test_db, "user_five_fails", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "user_five_fails") is True

    async def test_lockout_expires_after_window(self, test_db: AsyncSession):
        """Failed attempts older than LOCKOUT_WINDOW_MINUTES are not counted."""
        old_time = datetime.utcnow() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES + 1)
        from app.models.models import LoginAttempt

        for _ in range(LOCKOUT_ATTEMPTS):
            attempt = LoginAttempt(
                username="user_expired",
                ip_address="10.0.0.1",
                attempted_at=old_time,
                success=0,
            )
            test_db.add(attempt)
        await test_db.commit()

        assert await check_lockout(test_db, "user_expired") is False

    async def test_success_does_not_count_toward_lockout(self, test_db: AsyncSession):
        """Successful attempts do not contribute to the lockout counter."""
        for _ in range(LOCKOUT_ATTEMPTS - 1):
            await record_attempt(test_db, "user_success_mix", "10.0.0.1", success=False)
        await record_attempt(test_db, "user_success_mix", "10.0.0.1", success=True)
        assert await check_lockout(test_db, "user_success_mix") is False

    async def test_different_users_independent(self, test_db: AsyncSession):
        """Locking one user does not affect another user."""
        for _ in range(LOCKOUT_ATTEMPTS):
            await record_attempt(test_db, "user_a_locked", "10.0.0.1", success=False)
        # user_b has no attempts
        assert await check_lockout(test_db, "user_b_independent") is False

    async def test_unlock_clears_lockout(self, test_db: AsyncSession):
        """After unlock_user(), the previously locked account is no longer locked."""
        for _ in range(LOCKOUT_ATTEMPTS):
            await record_attempt(test_db, "user_to_unlock", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "user_to_unlock") is True

        await unlock_user(test_db, "user_to_unlock")
        assert await check_lockout(test_db, "user_to_unlock") is False


class TestSmartLockout:
    """Smart lockout: users with active sessions bypass lockout."""

    async def test_regression_smart_lockout_bypass(self, test_db: AsyncSession):
        """
        Regression: a user with a recent successful login must NOT be locked out
        even when they have >= LOCKOUT_ATTEMPTS failed attempts in the window.

        Spec: Scenario "Lockout check with recent successful login"
        → WHEN user has successful login < 30 min ago
        → THEN check_lockout returns False
        """
        from app.models.models import LoginAttempt

        username = "admin_with_active_session"

        # Seed: LOCKOUT_ATTEMPTS failed attempts within the detection window
        for _ in range(LOCKOUT_ATTEMPTS):
            attempt = LoginAttempt(
                username=username,
                ip_address="192.168.1.100",
                attempted_at=datetime.utcnow() - timedelta(minutes=5),
                success=0,
            )
            test_db.add(attempt)

        # Seed: one successful login within the last RECENT_SESSION_MINUTES
        recent_success = LoginAttempt(
            username=username,
            ip_address="10.0.0.50",
            attempted_at=datetime.utcnow() - timedelta(minutes=15),
            success=1,
        )
        test_db.add(recent_success)
        await test_db.commit()

        # Must NOT be locked — smart lockout bypasses because session is active
        assert await check_lockout(test_db, username) is False

    async def test_has_recent_session_returns_true_when_recent_success(
        self, test_db: AsyncSession
    ):
        """has_recent_session() returns True when a recent successful attempt exists."""
        from app.models.models import LoginAttempt

        username = "user_recent_success"
        attempt = LoginAttempt(
            username=username,
            ip_address="10.0.0.1",
            attempted_at=datetime.utcnow() - timedelta(minutes=10),
            success=1,
        )
        test_db.add(attempt)
        await test_db.commit()

        assert await has_recent_session(test_db, username) is True

    async def test_has_recent_session_returns_false_when_no_success(
        self, test_db: AsyncSession
    ):
        """has_recent_session() returns False when there are no recent successful logins."""
        assert await has_recent_session(test_db, "user_no_success_ever") is False

    async def test_has_recent_session_returns_false_for_old_success(
        self, test_db: AsyncSession
    ):
        """has_recent_session() returns False for successful logins older than 30 min."""
        from app.models.models import LoginAttempt

        username = "user_old_success"
        old_success = LoginAttempt(
            username=username,
            ip_address="10.0.0.1",
            attempted_at=datetime.utcnow()
            - timedelta(minutes=RECENT_SESSION_MINUTES + 5),
            success=1,
        )
        test_db.add(old_success)
        await test_db.commit()

        assert await has_recent_session(test_db, username) is False

    async def test_lockout_applies_without_recent_session(self, test_db: AsyncSession):
        """
        Without a recent session, lockout applies normally after LOCKOUT_ATTEMPTS fails.

        Spec: Scenario "User without active session gets locked out"
        """
        from app.models.models import LoginAttempt

        username = "user_no_session_locked"

        # Only failed attempts — no success
        for _ in range(LOCKOUT_ATTEMPTS):
            attempt = LoginAttempt(
                username=username,
                ip_address="10.0.0.2",
                attempted_at=datetime.utcnow() - timedelta(minutes=2),
                success=0,
            )
            test_db.add(attempt)
        await test_db.commit()

        assert await check_lockout(test_db, username) is True
