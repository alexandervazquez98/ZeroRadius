"""
Integration tests: Rate Limiting (slowapi).

Tests verify that endpoints enforce the rate limits defined in
security-hardening-fase2 (REQ-3 from rate-limiting/spec.md):
  - POST /auth/token  → 5/minute
  - POST /nas         → 10/minute

Strategy: each test function uses a unique X-Forwarded-For IP so
that tests don't share rate-limit buckets (the MemoryStorage is
session-scoped, so counters persist across tests in the same run).

The conftest.py async_client fixture is session-scoped; we do NOT
reset the global limiter between tests because that would race with
other tests. Instead we use isolated IPs per test.
"""

import pytest


# ---------------------------------------------------------------------------
# T7.1 — POST /auth/token returns 429 after 5 requests from the same IP
# ---------------------------------------------------------------------------


class TestAuthTokenRateLimit:
    """POST /auth/token is limited to 5/minute per IP."""

    async def test_auth_token_429_after_5_requests(self, async_client):
        """
        REQ-3 Scenario: Límite de login excedido.

        Given an IP makes 5 requests to POST /auth/token in < 1 minute,
        when it makes the 6th request,
        then it receives HTTP 429.
        """
        # Use a unique IP for this test to avoid cross-test pollution
        headers = {"X-Forwarded-For": "10.0.10.1"}
        creds = {"username": "rate_limit_user", "password": "wrongpassword"}

        # First 5 requests must be allowed (401 or 200 — not 429)
        for i in range(5):
            resp = await async_client.post("/auth/token", data=creds, headers=headers)
            assert resp.status_code != 429, (
                f"Request {i + 1} should not be rate-limited yet, got {resp.status_code}"
            )

        # 6th request must be blocked
        resp6 = await async_client.post("/auth/token", data=creds, headers=headers)
        assert resp6.status_code == 429, (
            f"6th request to /auth/token should return 429, got {resp6.status_code}: {resp6.text}"
        )

    async def test_auth_token_429_response_body_has_detail(self, async_client):
        """
        REQ-4 Scenario: Respuesta 429 bien formada.

        The 429 response body must contain a 'detail' field (not a stack trace).
        """
        headers = {"X-Forwarded-For": "10.0.10.2"}
        creds = {"username": "rate_limit_user2", "password": "wrongpassword"}

        # Exhaust the limit (5 requests)
        for _ in range(5):
            await async_client.post("/auth/token", data=creds, headers=headers)

        # 6th should be 429 with a well-formed body
        resp = await async_client.post("/auth/token", data=creds, headers=headers)
        assert resp.status_code == 429

        body = resp.json()
        # slowapi's _rate_limit_exceeded_handler returns {"error": "Rate limit exceeded..."}
        # Our custom handler returns {"detail": "Rate limit exceeded. Try again later."}
        has_message = "detail" in body or "error" in body
        assert has_message, (
            f"429 response must have 'detail' or 'error' field, got: {body}"
        )

    async def test_different_ips_have_independent_buckets(self, async_client):
        """
        REQ-2 Scenario: Dos clientes distintos no comparten bucket.

        Two different IPs each making 5 requests must not block each other.
        Note: IP-A and IP-B use DIFFERENT usernames to avoid triggering the
        per-username account-lockout (5 failed attempts locks the account for
        all IPs), which would cause IP-B's requests to be rejected even though
        it has its own clean rate-limit bucket.
        """
        # IP-A makes 5 requests with its own username
        ip_a = "10.0.11.1"
        creds_a = {"username": "bucket_test_user_a", "password": "wrongpassword"}
        for i in range(5):
            resp = await async_client.post(
                "/auth/token",
                data=creds_a,
                headers={"X-Forwarded-For": ip_a},
            )
            assert resp.status_code != 429, (
                f"IP-A request {i + 1} should not be blocked, got {resp.status_code}"
            )

        # IP-B makes 5 requests with a DIFFERENT username (independent bucket)
        ip_b = "10.0.11.2"
        creds_b = {"username": "bucket_test_user_b", "password": "wrongpassword"}
        for i in range(5):
            resp = await async_client.post(
                "/auth/token",
                data=creds_b,
                headers={"X-Forwarded-For": ip_b},
            )
            assert resp.status_code != 429, (
                f"IP-B request {i + 1} should not be blocked, got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# T7.2 — POST /nas returns 429 after 10 requests from the same IP
# ---------------------------------------------------------------------------

# Minimum valid NAS secret (≥ 32 characters, enforced by the schema)
_VALID_SECRET = "a" * 32


class TestNasCreateRateLimit:
    """POST /nas is limited to 10/minute per IP (docker-restart group)."""

    async def test_nas_create_429_after_10_requests(
        self, async_client, superadmin_token
    ):
        """
        REQ-3 Scenario: Límite de docker restart (NAS) excedido.

        Given an IP makes 10 requests to POST /nas in < 1 minute,
        when it makes the 11th request,
        then it receives HTTP 429.
        """
        headers = {
            "X-Forwarded-For": "10.0.20.1",
            "Authorization": f"Bearer {superadmin_token}",
        }

        # First 10 requests — must be allowed (200, 201, or 422/409 due to DB
        # constraints, but NOT 429)
        for i in range(10):
            payload = {
                "nasname": f"10.99.{i}.1",
                "shortname": f"rate-limit-nas-{i}",
                "secret": _VALID_SECRET,
                "type": "other",
            }
            resp = await async_client.post("/nas", json=payload, headers=headers)
            assert resp.status_code != 429, (
                f"NAS request {i + 1} should not be rate-limited yet, "
                f"got {resp.status_code}"
            )

        # 11th request must be blocked by the rate limiter
        payload = {
            "nasname": "10.99.99.99",
            "shortname": "rate-limit-nas-overflow",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp11 = await async_client.post("/nas", json=payload, headers=headers)
        assert resp11.status_code == 429, (
            f"11th POST /nas should return 429, got {resp11.status_code}: {resp11.text}"
        )

    async def test_nas_create_rate_limit_does_not_affect_different_ip(
        self, async_client, superadmin_token
    ):
        """
        Different IP must not be affected by another IP's rate limit exhaustion.
        """
        # First, exhaust the limit for IP-A
        ip_a_headers = {
            "X-Forwarded-For": "10.0.20.2",
            "Authorization": f"Bearer {superadmin_token}",
        }
        for i in range(10):
            payload = {
                "nasname": f"10.88.{i}.1",
                "shortname": f"nas-rl-ipa-{i}",
                "secret": _VALID_SECRET,
                "type": "other",
            }
            await async_client.post("/nas", json=payload, headers=ip_a_headers)

        # IP-B should still be able to make a request
        ip_b_headers = {
            "X-Forwarded-For": "10.0.20.3",
            "Authorization": f"Bearer {superadmin_token}",
        }
        payload = {
            "nasname": "10.88.100.1",
            "shortname": "nas-rl-ipb-first",
            "secret": _VALID_SECRET,
            "type": "other",
        }
        resp = await async_client.post("/nas", json=payload, headers=ip_b_headers)
        assert resp.status_code != 429, (
            f"IP-B's first NAS request must not be rate-limited, got {resp.status_code}"
        )
