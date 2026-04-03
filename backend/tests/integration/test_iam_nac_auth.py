"""
Integration tests: IAM-NAC endpoint authentication and authorization.

Tests verify requirements from security-hardening-fase2/specs/iam-nac-auth/spec.md:
  - REQ-1 / REQ-5: All IAM-NAC endpoints require a valid JWT (401 without token)
  - REQ-3 / REQ-6: Write endpoints require admin+ role (403 for lower roles)
  - REQ-2: GET endpoints are accessible to any authenticated user (200 for viewer+)

Roles tested:
  - readonly  → lowest privilege (similar to viewer in the spec)
  - helpdesk  → operator-level (below admin)
  - admin     → write access (admin or superadmin)
  - superadmin → highest privilege

Note on IP isolation: these tests send authenticated requests. Since the
session-scoped async_client accumulates rate-limit counters, we use a
dedicated X-Forwarded-For IP ("10.0.30.x") for IAM-NAC auth tests so
we don't hit the 30/minute CRUD limit across the full test suite.
"""

import pytest


class TestIAMNACNoToken:
    """REQ-1 / REQ-5: Requests without a JWT must receive 401 Unauthorized."""

    async def test_get_zones_without_token_returns_401(self, async_client):
        """
        Scenario: Request sin token es rechazada.

        Given GET /iam-nac/zones with no Authorization header,
        when the server evaluates the request,
        then it returns HTTP 401.
        """
        resp = await async_client.get("/iam-nac/zones")
        assert resp.status_code == 401, (
            f"GET /iam-nac/zones without token should return 401, got {resp.status_code}"
        )

    async def test_get_roles_without_token_returns_401(self, async_client):
        """GET /iam-nac/roles without Authorization returns 401."""
        resp = await async_client.get("/iam-nac/roles")
        assert resp.status_code == 401

    async def test_get_macros_without_token_returns_401(self, async_client):
        """GET /iam-nac/macros without Authorization returns 401."""
        resp = await async_client.get("/iam-nac/macros")
        assert resp.status_code == 401

    async def test_post_zones_without_token_returns_401(self, async_client):
        """POST /iam-nac/zones without Authorization returns 401, not 403."""
        payload = {"name": "no-auth-zone", "description": "test"}
        resp = await async_client.post("/iam-nac/zones", json=payload)
        # Must be 401 (unauthenticated), NOT 403 (authenticated but forbidden)
        assert resp.status_code == 401, (
            f"POST /iam-nac/zones without token should return 401, got {resp.status_code}"
        )


class TestIAMNACInsufficientRole:
    """
    REQ-3 / REQ-6: Write endpoints require admin or superadmin.

    Users with viewer/helpdesk/readonly roles must receive 403 on write endpoints.
    """

    async def test_readonly_cannot_post_zones_returns_403(
        self, async_client, readonly_token
    ):
        """
        Scenario: Viewer intenta crear una zona.

        Given a user with role 'readonly' has a valid JWT,
        when they POST /iam-nac/zones,
        then they receive HTTP 403 Forbidden.
        """
        payload = {"name": "forbidden-zone", "description": "should fail"}
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403, (
            f"readonly role should get 403 on POST /iam-nac/zones, got {resp.status_code}"
        )

    async def test_helpdesk_cannot_post_zones_returns_403(
        self, async_client, helpdesk_token
    ):
        """
        Helpdesk (operator-level) must be rejected on POST /iam-nac/zones.
        """
        payload = {"name": "helpdesk-zone", "description": "should fail"}
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403, (
            f"helpdesk role should get 403 on POST /iam-nac/zones, got {resp.status_code}"
        )

    async def test_auditor_cannot_post_zones_returns_403(
        self, async_client, auditor_token
    ):
        """Auditor must be rejected on POST /iam-nac/zones (write operation)."""
        payload = {"name": "auditor-zone", "description": "should fail"}
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 403, (
            f"auditor role should get 403 on POST /iam-nac/zones, got {resp.status_code}"
        )

    async def test_403_body_indicates_insufficient_permissions(
        self, async_client, readonly_token
    ):
        """
        REQ-6: The 403 message must indicate permissions issue, not missing token.
        """
        payload = {"name": "forbidden-zone-2", "description": "should fail"}
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "detail" in body, f"403 response must have 'detail', got: {body}"
        # The message should be about permissions, not about missing auth
        detail = body["detail"].lower()
        assert (
            "permission" in detail or "forbidden" in detail or "insufficient" in detail
        ), f"403 body should indicate permission issue, got: {body['detail']}"


class TestIAMNACAuthorizedAccess:
    """
    REQ-2: GET endpoints are accessible to any authenticated role.
    Admin+ can use write endpoints.
    """

    async def test_get_zones_with_admin_token_returns_200(
        self, async_client, admin_token
    ):
        """
        Scenario: Request con token válido pasa la validación de identidad.

        Given a valid JWT for admin,
        when GET /iam-nac/zones is requested,
        then the server returns HTTP 200 with a list.
        """
        resp = await async_client.get(
            "/iam-nac/zones",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200, (
            f"admin token should get 200 on GET /iam-nac/zones, got {resp.status_code}"
        )
        assert isinstance(resp.json(), list), (
            f"GET /iam-nac/zones should return a list, got: {resp.json()}"
        )

    async def test_get_zones_with_readonly_token_returns_200(
        self, async_client, readonly_token
    ):
        """
        REQ-2 Scenario: Viewer accede a lectura de zonas.

        Given a user with role 'readonly' (lowest privilege),
        when GET /iam-nac/zones is requested with a valid token,
        then the server returns HTTP 200.
        """
        resp = await async_client.get(
            "/iam-nac/zones",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 200, (
            f"readonly token should get 200 on GET /iam-nac/zones, got {resp.status_code}"
        )

    async def test_get_zones_with_helpdesk_token_returns_200(
        self, async_client, helpdesk_token
    ):
        """Helpdesk can read IAM-NAC zones."""
        resp = await async_client.get(
            "/iam-nac/zones",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 200

    async def test_get_zones_with_auditor_token_returns_200(
        self, async_client, auditor_token
    ):
        """Auditor can read IAM-NAC zones."""
        resp = await async_client.get(
            "/iam-nac/zones",
            headers={"Authorization": f"Bearer {auditor_token}"},
        )
        assert resp.status_code == 200

    async def test_get_zones_with_superadmin_token_returns_200(
        self, async_client, superadmin_token
    ):
        """Superadmin can read IAM-NAC zones."""
        resp = await async_client.get(
            "/iam-nac/zones",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code == 200

    async def test_admin_can_post_zones(self, async_client, admin_token):
        """
        REQ-3 Scenario: Admin crea una zona.

        Given admin role JWT,
        when POST /iam-nac/zones with valid payload,
        then the response is 200 or 201.
        """
        payload = {
            "name": "admin-created-zone",
            "description": "Zone created by admin in test",
        }
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # 200 or 201 on successful creation
        assert resp.status_code in (200, 201), (
            f"admin should be able to POST /iam-nac/zones, got {resp.status_code}: {resp.text}"
        )

    async def test_superadmin_can_post_zones(self, async_client, superadmin_token):
        """Superadmin can create IAM-NAC zones."""
        payload = {
            "name": "superadmin-created-zone",
            "description": "Zone created by superadmin in test",
        }
        resp = await async_client.post(
            "/iam-nac/zones",
            json=payload,
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        assert resp.status_code in (200, 201), (
            f"superadmin should be able to POST /iam-nac/zones, got {resp.status_code}: {resp.text}"
        )
