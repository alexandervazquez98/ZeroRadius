"""
T38 — Unit tests for LockoutService.

Uses an in-memory SQLite test_db fixture (from conftest.py).

Tests cover:
- No attempts → not locked
- 4 failed attempts → not locked
- 5 failed attempts → locked
- Expired lockout (attempts older than LOCKOUT_DURATION_MINUTES) → not locked
- Successful attempt does not contribute to lockout
- Different users are independent
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.lockout import (
    check_lockout,
    record_attempt,
    unlock_user,
    LOCKOUT_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
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
        """Failed attempts older than LOCKOUT_DURATION_MINUTES are not counted."""
        old_time = datetime.utcnow() - timedelta(minutes=LOCKOUT_DURATION_MINUTES + 1)
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
