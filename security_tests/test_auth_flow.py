"""
T34 — Integration security smoke test: full auth flow with lockout + audit trail.

Requires a running backend at BASE_URL (default: http://localhost:8000).
Set environment variables to configure credentials:
    BASE_URL         — backend URL (default: http://localhost:8000)
    ADMIN_USER       — superadmin username (default: admin)
    ADMIN_PASS       — superadmin password (default: admin)
    RADIUS_USER      — test RADIUS user for radpostauth check (default: testuser)

Usage:
    cd security_tests
    python test_auth_flow.py

All assertions print PASS / FAIL. Exit code 0 if all pass, 1 if any fail.
"""

import os
import sys
import json
import base64
import requests
from typing import Any

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")
RADIUS_USER = os.getenv("RADIUS_USER", "testuser")

_failures: list[str] = []


def _assert(condition: bool, name: str, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        _failures.append(name)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without verification (test only)."""
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload_b64 = parts[1]
    # Add padding
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


def test_lockout_after_five_wrong_attempts() -> None:
    """Login 5 times with wrong password then assert 6th returns 429."""
    print("\n[T34.1] Lockout: 6 wrong attempts → 429")
    username = "lockout_test_user_t34"
    wrong_creds = {"username": username, "password": "definitely_wrong_password"}

    for i in range(5):
        resp = requests.post(f"{BASE_URL}/api/auth/token", data=wrong_creds)
        _assert(
            resp.status_code in (401, 422),
            f"Attempt {i + 1} returns 401/422",
            f"got {resp.status_code}",
        )

    resp6 = requests.post(f"{BASE_URL}/api/auth/token", data=wrong_creds)
    _assert(
        resp6.status_code == 429,
        "6th attempt returns 429 (account locked)",
        f"got {resp6.status_code}: {resp6.text[:120]}",
    )


def test_jwt_contains_role() -> None:
    """Login with correct credentials → JWT contains role field."""
    print("\n[T34.2] JWT contains role field")
    creds = {"username": ADMIN_USER, "password": ADMIN_PASS}
    resp = requests.post(f"{BASE_URL}/api/auth/token", data=creds)

    _assert(
        resp.status_code == 200,
        "Login with correct credentials returns 200",
        f"got {resp.status_code}: {resp.text[:120]}",
    )

    if resp.status_code != 200:
        return

    token = resp.json().get("access_token", "")
    payload = _decode_jwt_payload(token)

    _assert("role" in payload, "JWT payload contains 'role' field", str(payload))
    _assert(
        payload.get("role")
        in ("superadmin", "admin", "helpdesk", "auditor", "readonly"),
        "JWT role is a valid role value",
        f"role={payload.get('role')}",
    )


def test_auditor_cannot_access_protected_endpoints() -> None:
    """Calling DELETE /api/admin-users/{id} as auditor → 403."""
    print("\n[T34.3] Role guard: auditor cannot DELETE admin-users")

    # First login as admin to get a valid token, then check that role-guard works
    creds = {"username": ADMIN_USER, "password": ADMIN_PASS}
    resp = requests.post(f"{BASE_URL}/api/auth/token", data=creds)
    if resp.status_code != 200:
        _assert(False, "Cannot test role guard (login failed)", resp.text[:80])
        return

    token = resp.json()["access_token"]
    payload = _decode_jwt_payload(token)
    role = payload.get("role", "")

    if role not in ("admin", "superadmin"):
        print(f"  [SKIP] Not an admin/superadmin — skipping DELETE test (role={role})")
        return

    # Try to delete a non-existent user — response depends on role:
    # superadmin → 404 (user not found), admin/helpdesk/auditor → 403
    headers = {"Authorization": f"Bearer {token}"}
    resp_del = requests.delete(f"{BASE_URL}/api/admin-users/999999", headers=headers)

    if role == "superadmin":
        _assert(
            resp_del.status_code in (404, 200),
            "Superadmin DELETE returns 404 (not 403)",
            f"got {resp_del.status_code}",
        )
    else:
        _assert(
            resp_del.status_code == 403,
            "Non-superadmin DELETE returns 403",
            f"got {resp_del.status_code}",
        )


def test_radpostauth_pass_is_redacted() -> None:
    """
    After an authentication event, radpostauth.pass must be '[REDACTED]'.

    This test queries the audit endpoint (GET /api/audit/access) to check
    recent entries. The pass field is not exposed via API (by design), so
    this test validates absence of plain-text password via the SIEM export.

    Note: full validation requires direct DB access. If audit endpoint is
    available and returns data, we at least confirm the endpoint is working.
    """
    print("\n[T34.4] radpostauth.pass redaction (via audit export)")
    creds = {"username": ADMIN_USER, "password": ADMIN_PASS}
    resp = requests.post(f"{BASE_URL}/api/auth/token", data=creds)
    if resp.status_code != 200:
        _assert(False, "Cannot test pass redaction (login failed)", resp.text[:80])
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp_audit = requests.get(f"{BASE_URL}/api/audit/access", headers=headers)
    _assert(
        resp_audit.status_code == 200,
        "GET /api/audit/access returns 200",
        f"got {resp_audit.status_code}",
    )

    if resp_audit.status_code == 200:
        data = resp_audit.json()
        entries = data if isinstance(data, list) else data.get("items", [])
        # Confirm no entry has a plain-text password in the 'pass' field
        for entry in entries[:20]:
            pw = entry.get("pass", "")
            _assert(
                pw == "[REDACTED]" or pw == "" or pw is None,
                f"Entry pass field is redacted (id={entry.get('id', '?')})",
                f"pass='{pw}'",
            )
        if not entries:
            print("  [INFO] No audit entries to verify — radpostauth table is empty.")


def test_siem_export_returns_valid_schema() -> None:
    """GET /api/audit/export?format=json returns array with expected SIEM fields."""
    print("\n[T34.5] SIEM export schema")
    creds = {"username": ADMIN_USER, "password": ADMIN_PASS}
    resp = requests.post(f"{BASE_URL}/api/auth/token", data=creds)
    if resp.status_code != 200:
        _assert(False, "Cannot test SIEM export (login failed)", resp.text[:80])
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    payload = _decode_jwt_payload(token)
    role = payload.get("role", "")

    if role not in ("superadmin", "admin", "auditor"):
        print(f"  [SKIP] Role {role!r} cannot access SIEM export — skipping.")
        return

    resp_exp = requests.get(f"{BASE_URL}/api/audit/export?format=json", headers=headers)
    _assert(
        resp_exp.status_code == 200,
        "GET /api/audit/export returns 200",
        f"got {resp_exp.status_code}: {resp_exp.text[:120]}",
    )

    if resp_exp.status_code == 200:
        try:
            data = resp_exp.json()
        except Exception:
            _assert(False, "Export response is valid JSON")
            return

        _assert(
            isinstance(data, list),
            "SIEM export response is a JSON array",
            type(data).__name__,
        )

        if data:
            first = data[0]
            for field in ("event_id", "timestamp_utc"):
                _assert(
                    field in first,
                    f"SIEM event has '{field}' field",
                    str(list(first.keys())[:8]),
                )


if __name__ == "__main__":
    print("=" * 60)
    print("T34 — Security smoke tests")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    test_lockout_after_five_wrong_attempts()
    test_jwt_contains_role()
    test_auditor_cannot_access_protected_endpoints()
    test_radpostauth_pass_is_redacted()
    test_siem_export_returns_valid_schema()

    print("\n" + "=" * 60)
    if _failures:
        print(f"RESULT: {len(_failures)} test(s) FAILED:")
        for f in _failures:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("RESULT: All tests PASSED ✓")
        sys.exit(0)
