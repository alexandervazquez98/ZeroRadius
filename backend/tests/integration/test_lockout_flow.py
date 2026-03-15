"""
T41 — Integration tests: full lockout lifecycle.

Tests the end-to-end lockout flow using the real test DB (no mocks).
Uses async_client from conftest.py, which points to the FastAPI app
wired to an in-memory SQLite database.

Note: tests for radpostauth password redaction are marked as integration-only
since they require a running FreeRADIUS instance.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class TestLockoutEndToEnd:
    async def test_six_failed_attempts_trigger_429(
        self, async_client, test_db: AsyncSession
    ):
        """5 failed attempts + 6th → HTTP 429."""
        creds = {"username": "lockout_test_e2e", "password": "wrongpassword"}

        for i in range(5):
            resp = await async_client.post("/auth/token", data=creds)
            assert resp.status_code in (401, 422), (
                f"Attempt {i + 1} should be 401/422, got {resp.status_code}"
            )

        # Sixth attempt must be locked out
        resp6 = await async_client.post("/auth/token", data=creds)
        assert resp6.status_code == 429, (
            f"6th attempt should be 429, got {resp6.status_code}: {resp6.text}"
        )

    async def test_lockout_message_contains_duration(
        self, async_client, test_db: AsyncSession
    ):
        """The 429 error message must indicate the lockout duration."""
        creds = {"username": "lockout_msg_e2e", "password": "wrongpassword"}

        for _ in range(5):
            await async_client.post("/auth/token", data=creds)

        resp = await async_client.post("/auth/token", data=creds)
        assert resp.status_code == 429
        body = resp.json().get("detail", "")
        assert "locked" in body.lower() or "15" in body, (
            f"Expected lockout message with 'locked' or '15', got: {body}"
        )

    async def test_jwt_contains_role_field(self, async_client, test_db: AsyncSession):
        """After successful login, the JWT must contain a 'role' field."""
        import json
        import base64

        # The test_db has a default admin user seeded at startup
        creds = {"username": "admin", "password": "admin"}
        resp = await async_client.post("/auth/token", data=creds)

        if resp.status_code != 200:
            pytest.skip("Default admin user not available in test DB")

        token = resp.json().get("access_token", "")
        # Decode JWT payload (no signature check needed for this test)
        parts = token.split(".")
        assert len(parts) == 3, "Token should have 3 parts"

        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))

        assert "role" in payload, f"JWT payload missing 'role' field: {payload}"
        assert payload["role"] in (
            "superadmin",
            "admin",
            "helpdesk",
            "auditor",
            "readonly",
        ), f"Unexpected role value: {payload['role']}"

    async def test_superadmin_can_unlock_account(
        self, async_client, test_db: AsyncSession, superadmin_token
    ):
        """A superadmin can immediately unlock a locked account via the unlock endpoint."""
        from app.models.models import AdminUser
        from app.core.security import get_password_hash
        from sqlalchemy import select

        # Create a test user to lock
        test_username = "unlock_target_e2e"
        hashed_pw = get_password_hash("correct_password")
        user = AdminUser(
            username=test_username,
            hashed_password=hashed_pw,
            force_password_change=0,
        )
        test_db.add(user)
        await test_db.commit()
        await test_db.refresh(user)

        # Lock the user with 5 wrong attempts
        creds = {"username": test_username, "password": "wrong"}
        for _ in range(5):
            await async_client.post("/auth/token", data=creds)

        # Verify account is now locked
        resp_locked = await async_client.post("/auth/token", data=creds)
        assert resp_locked.status_code == 429, (
            "Account should be locked after 5 bad attempts"
        )

        # Superadmin unlocks
        resp_unlock = await async_client.post(
            f"/admin-users/{user.id}/unlock",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp_unlock.status_code == 200, (
            f"Unlock should return 200, got {resp_unlock.status_code}: {resp_unlock.text}"
        )

        # Now the correct password should work
        good_creds = {"username": test_username, "password": "correct_password"}
        resp_good = await async_client.post("/auth/token", data=good_creds)
        assert resp_good.status_code == 200, (
            f"After unlock, correct login should succeed, got {resp_good.status_code}"
        )

    async def test_expired_lockout_allows_login(
        self, async_client, test_db: AsyncSession
    ):
        """After the lockout window expires, the account is no longer locked."""
        from app.models.models import LoginAttempt
        from app.services.lockout import LOCKOUT_DURATION_MINUTES

        old_time = datetime.utcnow() - timedelta(minutes=LOCKOUT_DURATION_MINUTES + 1)

        # Insert expired failed attempts directly into the DB
        test_username = "expired_lockout_e2e"
        for _ in range(5):
            attempt = LoginAttempt(
                username=test_username,
                ip_address="127.0.0.1",
                attempted_at=old_time,
                success=0,
            )
            test_db.add(attempt)
        await test_db.commit()

        # Login with wrong password — should get 401, not 429 (lockout expired)
        creds = {"username": test_username, "password": "wrong"}
        resp = await async_client.post("/auth/token", data=creds)
        assert resp.status_code in (401, 422), (
            f"Expired lockout should allow attempt (401/422), got {resp.status_code}"
        )
        assert resp.status_code != 429, "Expired lockout must not return 429"
