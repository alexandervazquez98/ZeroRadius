---
goal: Map ZeroRadius's security controls and test coverage to the OWASP Top 10:2021 (and JWT / rate-limiting cross-cutting concerns), so an AI agent can reason about threat model coverage.
audience: agent + human
prerequisites:
  - Familiarity with OWASP Top 10:2021
  - Familiarity with FastAPI / SQLAlchemy / JWT
inputs: none
outputs: a per-AOx control × test matrix
---

# Security Coverage

> Threat model: **authenticated operator** vs. **unauthenticated attacker
> probing the REST API and WebSocket surface**. External attackers cannot
> reach FreeRADIUS directly unless the host ports `1812/udp` / `1813/udp`
> are exposed to the WAN (do not do this).
>
> Threat categories below follow the OWASP Top 10:2021 naming.

## A01 — Broken Access Control / Path Traversal

**Threat:** An attacker (authenticated or not) manipulates request inputs
to traverse the filesystem via the dictionary upload / rename endpoints,
or escalates by hitting admin-only endpoints with a read-only token.

**Controls:**
- Path validator (`app/services/dictionary_loader.py` `validate_path`)
  rejects `..`, absolute paths, and shell metacharacters.
- Role-based authorization via FastAPI `Depends(require_roles(...))` chains.
- All mutating endpoints require `admin` or `superadmin`; reads split
  across `auditor`, `admin`, `superadmin`.

**Tests:**
- `backend/tests/integration/test_security_a01_path_traversal.py`
  - `test_validate_path_traversal_rejected`
  - `test_validate_path_absolute_rejected`
  - `test_validate_path_valid_filename_ok`
- `backend/tests/integration/test_security_a01_roles.py`
  - `test_admin_users_readonly_forbidden` (auditor hits admin-only → 403)
  - `test_admin_users_admin_ok`
  - additional role-isolation tests

## A02 — Cryptographic Failures

**Threat:** Sensitive data (passwords, JWT secrets) leaks via misconfigured
TLS, weak hashing, or secrets stored in plaintext.

**Controls:**
- Bcrypt for admin password hashing (`passlib[bcrypt]`).
- JWT signed with `SECRET_KEY` (≥ 32 chars enforced at startup;
  application **crashes** if unset).
- HTTPS supported via the frontend Nginx with mounted `certs/`.
- Syslog ingestion authenticated via `SYSLOG_API_KEY` (header `X-API-Key`).
- `.env` is gitignored; `.env.example` carries no secret material.

**Tests:**
- `backend/tests/integration/test_security_jwt.py`
  - `test_jwt_wrong_secret_rejected`
  - `test_jwt_tampered_payload_rejected`
  - additional negative tests
- `backend/tests/unit/test_integrity.py` validates hashing primitives.

## A03 — Injection (SQL, command)

**Threat:** Attacker injects SQL or shell commands through user input.

**Controls:**
- SQLAlchemy 2.0 parameterized queries (no string-concatenation SQL anywhere).
- Pydantic v2 input validation on every request body and query parameter.
- No `eval` / `exec` on user data.

**Tests:**
- Implicitly covered by `backend/tests/integration/` — every endpoint test
  exercises the parameterization path.
- See A10 — input validators are tested independently.

## A04 — Insecure Design / Authentication

**Threat:** Weak password policy; lockout bypass; design flaws enabling
auth bypass.

**Controls:**
- Account lockout after N failed attempts (`app/services/lockout.py`).
- Password policy validators (length, character classes).
- Forced password change on first admin login (`force_password_change` middleware).
- Rate limiting on auth endpoints (slowapi; `30/minute` default).
- Role hierarchy: `superadmin > admin > auditor > readonly`.

**Tests:**
- `backend/tests/integration/test_security_a04_auth.py`
  - `TestPasswordPolicy::test_password_too_short_rejected`
  - `TestPasswordPolicy::test_password_no_special_rejected`
  - additional policy tests
- `backend/tests/integration/test_lockout_flow.py`
- `backend/tests/unit/test_lockout.py`

## A05 — Security Misconfiguration

**Threat:** Default credentials, unnecessary endpoints exposed (Swagger in
production), permissive CORS.

**Controls:**
- `DISABLE_DOCS=true` removes `/docs` and `/redoc` in production.
- `ALLOWED_ORIGINS` enumerates specific origins; `*` is rejected.
- `.env.example` carries placeholders, not secrets.
- Container healthchecks are explicit (DB ping, HTTP /health).
- First-admin bootstrap script refuses to run if an admin already exists.

**Tests:**
- Implicitly covered by `test-backend-fast.sh` (default test secret is
  string-fixed but distinct).
- Manual check in [`docs/deployment.md` → §7](deployment.md#security-implications).

## A06 — Vulnerable and Outdated Components

**Threat:** Known CVEs in dependencies.

**Controls:**
- Docker base images pinned to major versions (`mariadb:10.11`,
  `freeradius/freeradius-server:3.2.3`, `python:3.11-slim`).
- Production builds use `pip install --no-cache-dir` with no `pip install
  -U` in the Dockerfiles.
- Dependabot-style updates are not yet enabled (Phase 3 backlog).

**Tests:**
- Out of scope for the test pyramid; track via GitHub Dependabot config
  (planned).

## A07 — Identification and Authentication Failures

See **A04**. The two are intentionally merged in this catalog because
ZeroRadius's threats here are auth-centric.

Additional controls:
- JWT `exp` validated on every request.
- `aud` claim issued by the backend; mismatches rejected.
- Refresh tokens are **not** implemented; access token re-login is the
  re-auth path.

## A08 — Software and Data Integrity Failures

**Threat:** Attacker uploads a malicious dictionary file; the upload
endpoint accepts oversized files; integrity checks missing.

**Controls:**
- Dictionary upload size cap (configurable; default 1 MiB).
- Uploaded files parsed; lexicon validated before persistence.
- `run_pentest.py` (in `security_tests/`) is a manual pentest harness.

**Tests:**
- `backend/tests/integration/test_security_a08_upload.py`
  - `TestUploadSizeLimit::test_upload_within_limit_accepted`
  - additional size + content validation
- `security_tests/test_auth_flow.py` (manual pentest)

## A09 — Security Logging and Monitoring Failures

**Threat:** Auth events, admin actions, or changes are not logged.

**Controls:**
- `app_audit_log` records every admin write action
  (`table_affected`, `row_id`, `user`, `ip`, `timestamp`).
- `radius_reply_audit` records per-reply changes for access policies.
- `login_attempts` records all login outcomes (used by lockout).
- `radpostauth` records every FreeRADIUS post-auth decision.
- `syslog_events` records ingested network device syslog.

**Tests:**
- `backend/tests/integration/test_security_a09_audit.py`
  - `TestAuditCompleteness::test_failed_login_returns_401`
  - additional audit-emission tests

## A10 — Server-Side Request Forgery (SSRF) and Input Validation

**Threat:** Untrusted input reaches a downstream service or causes unsafe
state.

**Controls:**
- Pydantic v2 validators on every request body (`schemas/`).
- IP / CIDR validators reject hostnames, broadcast, loopback, and reserved
  ranges (depending on context).
- NAS name validated to reject ambiguous forms (post `nas-category-policy-hardening`).

**Tests:**
- `backend/tests/integration/test_security_a10_validators.py`
  - `TestNasnameValidator::test_nasname_invalid_format_rejected`
  - additional validators

## Cross-cutting: JWT

Beyond A02 / A07, JWT correctness is regression-tested in isolation.

**Tests:**
- `backend/tests/integration/test_security_jwt.py`
  - `TestJWTSecurity::test_jwt_wrong_secret_rejected`
  - `TestJWTSecurity::test_jwt_tampered_payload_rejected`
  - additional negative tests (alg=none, audience mismatch, etc.)

## Cross-cutting: Timing Oracles

**Threat:** Login duration reveals whether a username exists (timing
side-channel).

**Controls:**
- Bcrypt cost set to a constant; comparison runs even when the user is
  unknown.
- Constant-time response path for both "user not found" and "wrong password".

**Tests:**
- `backend/tests/integration/test_security_timing.py`
  - `TestTimingOracle::test_login_timing_oracle_mitigated`
  - measures response times for nonexistent vs. existing users.

## Coverage matrix

| OWASP | Control | Test(s) |
|---|---|---|
| A01 | Path validation, RBAC | `test_security_a01_path_traversal.py`, `test_security_a01_roles.py` |
| A02 | Bcrypt, JWT signing, secrets gating | `test_security_jwt.py`, `test_integrity.py` |
| A03 | SQLAlchemy parameterization, Pydantic validation | (covered across integration tests) + `test_security_a10_validators.py` |
| A04 | Lockout, password policy, rate limit | `test_security_a04_auth.py`, `test_lockout_flow.py`, `test_lockout.py` |
| A05 | `DISABLE_DOCS`, `ALLOWED_ORIGINS`, first-admin bootstrap | (manual via deployment.md §7) |
| A06 | Pinned base images | (planned via Dependabot) |
| A07 | See A04 | — |
| A08 | Upload size limits, dictionary validation | `test_security_a08_upload.py`, `security_tests/test_auth_flow.py` |
| A09 | `app_audit_log`, `login_attempts`, `radpostauth`, `syslog_events` | `test_security_a09_audit.py` |
| A10 | Pydantic validators, IP/CIDR format checks | `test_security_a10_validators.py` |
| JWT | `SECRET_KEY` enforcement, alg=none rejection, tampered payloads | `test_security_jwt.py` |
| Timing | Constant-time login response | `test_security_timing.py` |

## Open gaps (Phase 3 backlog)

- **A06 Dependabot** — automated CVE scanning is not yet configured.
- **A09 alerting** — there is no automatic alert channel when `audit_log`
  entries of a particular severity appear; manual review is the only flow.
- **A05 production hardening checklist** — no formalised "is this prod-ready"
  matrix beyond [`docs/deployment.md` §7](deployment.md#security-implications).

## Cross-references

- **Deployment / secrets:** [`docs/deployment.md`](deployment.md#environment-variables-canonical-list)
- **Architecture / live log viewer security:** [`docs/04-live-log-viewer.md`](04-live-log-viewer.md#security)
- **OWASP Top 10:2021 reference** — https://owasp.org/Top10/
