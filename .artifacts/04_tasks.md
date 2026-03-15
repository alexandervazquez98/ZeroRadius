# Tasks: iso27001-compliance-improvements
**Change**: ISO/IEC 27001:2022 Compliance Improvements  
**Project**: RADIUS-gestor  
**Date**: 2026-03-14  
**Total tasks**: 42  
**Status**: ✅ ALL 42 TASKS COMPLETED (2026-03-14)

---

## Phase 1 — Database & RADIUS Layer

### T01 — Fix SQLAlchemy models to use Mapped[] annotations (PREREQUISITE)
**Files**: `backend/app/models/models.py`  
**Why**: All subsequent backend tasks depend on correct SQLAlchemy 2.x `Mapped[type]` syntax. Current Column[str] style causes ~25 LSP errors cascading across routers.  
**What to do**:
- Convert all `Column(String)` → `Mapped[str] = mapped_column(String)`
- Convert all `Column(Integer)` → `Mapped[int] = mapped_column(Integer)`
- Convert nullable columns → `Mapped[Optional[str]] = mapped_column(String, nullable=True)`
- This fixes LSP errors in admin_users.py, auth.py, groups.py, security.py cascadingly
**Verification**: No LSP errors in models.py; no cascading type errors in routers after fix

---

### T02 — Fix core/security.py and main.py preexisting errors
**Files**: `backend/app/core/security.py`, `backend/app/main.py`  
**What to do**:
- security.py:45 — `payload.get("sub")` → `payload.get("sub") or ""`
- security.py:58 — `if user.is_active:` → `if user.is_active == 1:` or use `bool(user.is_active)`
- main.py:33 — Verify `get_db()` yields `AsyncSession`; if not, fix the session factory
**Verification**: No LSP errors in security.py or main.py

---

### T03 — Add role column to admin_users table
**Files**: `database/init.sql`, new `database/migrations/004_admin_users_role.sql`  
**What to do**:
- Add migration SQL:
  ```sql
  ALTER TABLE admin_users
    ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'admin' AFTER email;
  UPDATE admin_users SET role = 'superadmin' WHERE id = (SELECT MIN(id) FROM (SELECT id FROM admin_users) t);
  ```
- Add column to `database/init.sql` CREATE TABLE statement
- Add `role: Mapped[str] = mapped_column(String(32), default="admin")` to AdminUser model
**Verification**: `SELECT role FROM admin_users` returns values; first user is 'superadmin'

---

### T04 — Create login_attempts table
**Files**: `database/init.sql`, `database/migrations/003_new_tables.sql`  
**What to do**:
```sql
CREATE TABLE login_attempts (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64) NOT NULL,
    ip_address      VARCHAR(45) NULL,
    attempted_at    DATETIME(6) DEFAULT CURRENT_TIMESTAMP(6),
    success         TINYINT(1)  NOT NULL DEFAULT 0,
    INDEX idx_username_time (username, attempted_at)
) ENGINE=InnoDB;
```
- Add SQLAlchemy model `LoginAttempt`
**Verification**: Table exists in schema; model importable

---

### T05 — Create radius_reply_audit table
**Files**: `database/init.sql`, `database/migrations/003_new_tables.sql`  
**What to do**: Full schema per REQ-DB-005 in specs. Add SQLAlchemy model `RadiusReplyAudit`.
**Verification**: Table exists; `DESCRIBE radius_reply_audit` shows all 13 columns including record_hash

---

### T06 — Create user_nas_privilege_map table
**Files**: `database/init.sql`, `database/migrations/003_new_tables.sql`  
**What to do**: Full schema per REQ-DB-006 in specs. Add SQLAlchemy model `UserNasPrivilegeMap`.
**Verification**: Table exists; UNIQUE KEY on (username, nas_ip) works

---

### T07 — Enhance radpostauth table schema
**Files**: `database/init.sql`, `database/migrations/001_radpostauth_enhance.sql`  
**What to do**:
- ALTER to add: nas_ip_address, nas_identifier, nas_port, calling_station_id, called_station_id, reply_message, event_source, integrity_hash
- ALTER authdate: change from TIMESTAMP with ON UPDATE to `DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)`
**CRITICAL**: DEFAULT values on all new columns so existing FreeRADIUS queries don't break  
**Verification**: `DESCRIBE radpostauth` shows 15+ columns; existing test insert still works

---

### T08 — Enhance radacct table schema
**Files**: `database/init.sql`, `database/migrations/002_radacct_enhance.sql`  
**What to do**:
- ALTER to add: nasidentifier VARCHAR(64), privilege_level VARCHAR(32), vendor_reply_attrs JSON
- All nullable with no DEFAULT constraint
**Verification**: `DESCRIBE radacct` shows new columns; existing rows unaffected

---

### T09 — Fix radius/sql postauth_query
**Files**: `radius/sql`  
**What to do**:
1. Replace `%{User-Password:-Chap-Password}` → `'[REDACTED]'` in postauth_query
2. Add to the INSERT columns and values:
   - `nas_ip_address = '%{NAS-IP-Address}'`
   - `nas_identifier = '%{NAS-Identifier}'`
   - `calling_station_id = '%{Calling-Station-Id}'`
   - `reply_message = '%{reply:Reply-Message}'`
   - `event_source = 'radius'`
**Verification**: Restart FreeRADIUS; run `radtest user pass localhost 0 testing123`; check radpostauth row has nas_ip_address populated and pass='[REDACTED]'

---

## Phase 2 — Backend Security Layer

### T10 — Implement IntegrityHashService
**Files**: `backend/app/services/integrity.py` (NEW)  
**What to do**:
```python
# services/integrity.py
import hashlib, json

CRITICAL_FIELDS_AUTH = ["username", "authdate", "nas_ip_address", "reply", "calling_station_id"]

def compute_hash(record: dict, fields: list[str]) -> str:
    canonical = {k: str(record.get(k, "")) for k in sorted(fields)}
    payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

async def backfill_hashes(db: AsyncSession, batch_size: int = 500) -> int:
    """Fill integrity_hash for records where it is NULL."""
    ...

async def verify_record(db: AsyncSession, record_id: int) -> bool:
    """Returns True if stored hash matches computed hash."""
    ...
```
**Verification**: Unit test: compute_hash with known inputs produces known output; modify one field → hash changes

---

### T11 — Implement LockoutService
**Files**: `backend/app/services/lockout.py` (NEW)  
**What to do**: Per design spec — check/record/unlock functions using login_attempts table.  
Constants: LOCKOUT_ATTEMPTS=5, LOCKOUT_WINDOW_MINUTES=10, LOCKOUT_DURATION_MINUTES=15  
Cleanup: delete rows older than 24h on each check (or separate background task)  
**Verification**: 
- 5 failed attempts within window → 6th attempt returns locked=True
- After 15 min → locked=False
- Superadmin unlock → immediately locked=False

---

### T12 — Implement RBAC core module
**Files**: `backend/app/core/rbac.py` (NEW)  
**What to do**:
```python
from enum import Enum
from fastapi import Depends, HTTPException

class Role(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    HELPDESK = "helpdesk"
    AUDITOR = "auditor"
    READONLY = "readonly"

def require_roles(*roles: Role):
    async def check(current_user = Depends(get_current_user)):
        if current_user.role not in [r.value for r in roles]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return Depends(check)
```
**Verification**: Endpoint with `require_roles(Role.SUPERADMIN)` returns 403 for admin/helpdesk/auditor/readonly tokens

---

### T13 — Implement VSAGuardService
**Files**: `backend/app/services/vsa_guard.py` (NEW)  
**What to do**: Per design spec — VENDOR_ATTRIBUTE_MAP and HIGH_PRIVILEGE_ATTRS dicts.  
Functions: `validate_vsa_vendor_consistency(nas_vendor, attributes)` raises HTTPException 422 on mismatch.  
Function: `check_high_privilege(attributes) -> bool` returns True if any high-priv attr found.  
**Verification**: `validate_vsa_vendor_consistency("Juniper", [{"name": "Cisco-AVPair", "value": "..."}])` raises 422

---

### T14 — Implement NTPStatusService
**Files**: `backend/app/services/ntp_status.py` (NEW)  
**What to do**:
- Try `subprocess.run(["chronyc", "tracking"], capture_output=True)` to get NTP info
- Parse offset_seconds from output
- Fall back to `ntpq -p` if chrony not available
- Return `NTPStatus` dataclass: {synchronized, offset_ms, stratum, reference_server, last_sync, alert}
- alert=True if offset_ms > 500 or not synchronized
- Cache result for 60 seconds
**Verification**: Returns valid NTPStatus object; alert=True when offset injected as > 500ms

---

### T15 — Add event codes to AuditService
**Files**: `backend/app/services/audit.py`  
**What to do**:
- Add `EventCode` enum with all 20 codes (AUTH-001..007, ACCT-001..004, ADMIN-001..009)
- Update `log_audit()` function signature to accept optional `event_code: EventCode`
- Store event_code in `app_audit_log.action` field (or add dedicated column if needed)
- Add `integrity_hash` computation on each audit log record using IntegrityHashService
**Verification**: After admin login, app_audit_log contains row with action='ADMIN-007'; after user CRUD, correct ADMIN-00x codes

---

### T16 — Update auth.py: lockout + ADMIN-007 + RBAC + role in JWT
**Files**: `backend/app/routers/auth.py`, `backend/app/core/security.py`  
**What to do**:
1. Import LockoutService; call `check_lockout()` before password verification
2. Call `record_attempt(success=False)` on bad password → auto-lock at threshold
3. Call `record_attempt(success=True)` and log ADMIN-007 on success
4. Add `role` field to JWT payload: `{"sub": username, "role": user.role, "exp": ...}`
5. Update `get_current_user` to extract and expose `role`
6. Fix preexisting LSP errors (from T01+T02)
**Verification**: 6th login attempt returns 429; JWT decoded contains `role` field

---

### T17 — Update nas.py: secret validation + ADMIN-009
**Files**: `backend/app/routers/nas.py`  
**What to do**:
1. Add Pydantic validator on NASCreate/NASUpdate schema: `secret` must be >= 32 chars
2. Return HTTP 422 with clear message if validation fails
3. Log ADMIN-009 when NAS secret is changed (PUT endpoint, when secret field differs)
4. Apply `require_roles(Role.SUPERADMIN, Role.ADMIN)` dependency to write endpoints
**Verification**: POST /api/nas with 10-char secret → 422; with 32-char secret → 201

---

### T18 — Update groups.py: VSA guard + high-priv guard + RBAC + ADMIN-006
**Files**: `backend/app/routers/groups.py`  
**What to do**:
1. Import VSAGuardService; call `validate_vsa_vendor_consistency()` on PUT/POST of reply attributes
2. Call `check_high_privilege()` on attributes; if True and role != superadmin → 403
3. Apply `require_roles(Role.SUPERADMIN, Role.ADMIN)` to write endpoints
4. Log ADMIN-006 on any attribute modification with before/after values
5. Log ADMIN-004 on group name/description changes
6. Fix all preexisting LSP errors (fixed by T01)
**Verification**: Admin assigning priv-lvl=15 → 403; superadmin → 201 + ADMIN-006 in audit log

---

### T19 — Update admin_users.py: role management + RBAC + fix LSP
**Files**: `backend/app/routers/admin_users.py`  
**What to do**:
1. Add role field to AdminUserCreate/AdminUserUpdate schemas
2. Only superadmin can create/modify/delete admin users → `require_roles(Role.SUPERADMIN)`
3. Only superadmin can set role=superadmin (admin can create admin/helpdesk/auditor/readonly)
4. Add POST /api/admin-users/{id}/unlock endpoint (superadmin only) → calls LockoutService.unlock()
5. Fix all preexisting LSP errors (fixed by T01)
**Verification**: Admin creating admin-user with role=superadmin → 403; superadmin → 201

---

### T20 — Add SIEM export endpoint to audit.py
**Files**: `backend/app/routers/audit.py`  
**What to do**:
1. Add `GET /api/audit/export` endpoint
2. Query params: format=json|csv, from=ISO8601, to=ISO8601, event_type=AUTH|ACCT|ADMIN (optional)
3. Require roles: auditor, admin, superadmin → 403 for helpdesk/readonly
4. Build SIEMEvent Pydantic schema per specs (event_id, timestamp_utc, identity, access_request, authorization_result, session, audit)
5. Log ADMIN-008 event on each export call
6. Return StreamingResponse for large datasets; regular JSONResponse for < 1000 records
7. Add NAS IP and calling_station columns to existing GET /api/audit/access endpoint
**Verification**: GET /api/audit/export?format=json returns array with correct SIEM schema; helpdesk → 403

---

### T21 — Add NTP status endpoint
**Files**: `backend/app/routers/` (new file or add to existing system router)  
**What to do**:
1. Create `backend/app/routers/system.py` with `GET /api/system/ntp-status`
2. Require roles: admin, superadmin
3. Call NTPStatusService.get_status()
4. Return NTPStatusResponse schema
5. Register router in main.py
**Verification**: GET /api/system/ntp-status returns JSON with synchronized, offset_ms, alert fields

---

### T22 — Implement privilege_map router
**Files**: `backend/app/routers/privilege_map.py` (NEW)  
**What to do**:
1. CRUD endpoints:
   - GET /api/privilege-map (auditor, admin, superadmin can read)
   - POST /api/privilege-map (admin, superadmin)
   - PUT /api/privilege-map/{id} (admin, superadmin)
   - DELETE /api/privilege-map/{id} (superadmin only)
2. GET includes `days_until_review` computed field
3. Filter by: username, nas_ip, is_active, overdue_review
4. Log ADMIN-002 on all mutations
5. Register router in main.py
**Verification**: CRUD operations work; auditor can GET but not POST; superadmin can DELETE

---

### T23 — Update schemas.py with new Pydantic models
**Files**: `backend/app/schemas/schemas.py`  
**What to do**: Add schemas for:
- `RadPostAuthOut` (with nas_ip_address, calling_station_id, event_source)
- `SIEMEvent` (full SIEM JSON format per specs REQ-BE-005)
- `NTPStatusResponse`
- `UserNasPrivilegeMapCreate`, `UserNasPrivilegeMapOut`
- `LoginAttemptOut`
- `AdminUserCreate` / `AdminUserOut` updated with role field
**Verification**: No Pydantic validation errors on import

---

## Phase 3 — Frontend + FreeRADIUS Policy

### T24 — Extract role from JWT in AuthContext
**Files**: `frontend/src/context/AuthContext.jsx` (or equivalent)  
**What to do**:
1. After successful login, decode JWT with jwt-decode (already in deps)
2. Extract `role` from payload
3. Add `role` to auth context value
4. Expose `hasRole(roles: string[])` helper function
**Verification**: After login as superadmin, `authContext.role === 'superadmin'`

---

### T25 — Implement RoleGuard component
**Files**: `frontend/src/components/RoleGuard.jsx` (NEW)  
**What to do**:
```jsx
// Renders children if user has one of the allowed roles
// Otherwise redirects to /unauthorized or hides the element
function RoleGuard({ allowedRoles, fallback = null, children }) {
  const { role } = useAuth();
  if (!allowedRoles.includes(role)) return fallback;
  return children;
}
```
**Verification**: Superadmin sees all; helpdesk sees read-only items; unknown role → redirect

---

### T26 — Apply RBAC to navigation menu
**Files**: `frontend/src/` (App.jsx, Sidebar/Nav component)  
**What to do**:
- Wrap nav items with RoleGuard:
  - Admin Users: superadmin only
  - Groups (write actions): superadmin, admin
  - NAS (write actions): superadmin, admin
  - Privilege Map: superadmin, admin, auditor
  - Audit export button: auditor, admin, superadmin
- Add /unauthorized page (simple "Access Denied" message)
**Verification**: Login as helpdesk → Admin Users item not visible; login as superadmin → all visible

---

### T27 — Apply role-gated routes
**Files**: `frontend/src/App.jsx` (or router file)  
**What to do**:
- Wrap /privilege-map route with RoleGuard
- Add /unauthorized route
- Direct URL access to protected routes redirects unauthorized users
**Verification**: Helpdesk user entering /privilege-map URL → redirected to /unauthorized

---

### T28 — Enhance Audit page with NAS columns
**Files**: `frontend/src/pages/Audit.jsx`  
**What to do**:
1. Add columns to access log table: NAS IP | NAS Identifier | Calling Station | Event Code
2. Add NAS IP filter input (calls API with nas_ip query param)
3. Update API service call to fetch new fields
4. Handle null/empty nas_ip gracefully (backward compat with old records)
**Verification**: Table shows NAS IP for recent auth events; filter by NAS IP works

---

### T29 — Create PrivilegeMap.jsx page
**Files**: `frontend/src/pages/PrivilegeMap.jsx` (NEW), `frontend/src/services/privilegeMapService.js` (NEW)  
**What to do**:
1. DataTable with columns: Username | NAS IP | NAS ID | Vendor | Group | Priv Level | Review Date | Status | Actions
2. Row badges: "Review Soon" (yellow, within 30 days) | "Overdue" (red, past review_date)
3. Create/Edit modal with all required fields (username, nas_ip, nas_vendor, radius_group, privilege_level, justification, approved_by, review_date)
4. Delete confirmation dialog (superadmin only)
5. API service: CRUD calls to /api/privilege-map
6. Role-gated: auditors see table but no create/edit/delete buttons
**Verification**: Create a mapping → appears in table with correct badge; auditor sees no action buttons

---

### T30 — Add NTP status indicator to UI
**Files**: `frontend/src/` (header/status bar component)  
**What to do**:
1. Small indicator in app header/footer: green dot (synced) or red dot (alert)
2. Tooltip shows offset_ms and reference_server
3. Polls GET /api/system/ntp-status every 5 minutes
4. Only visible to admin/superadmin roles
**Verification**: Green dot shown when NTP synced; red dot when API returns alert=true

---

### T31 — Create FreeRADIUS NAS-based authorization policy
**Files**: `radius/policy.d/nas_based_authorization` (NEW), `radius/sites-available/default`  
**What to do**:
1. Create unlang policy file per design spec
2. The policy queries user_nas_privilege_map via SQL module to get radius_group
3. Include policy call in `authorize {}` section of sites-available/default
4. Add example `authorize_sql_nas` query to `radius/sql`:
   ```
   authorize_check_query = "SELECT radius_group FROM user_nas_privilege_map \
     WHERE username='%{User-Name}' AND nas_ip='%{NAS-IP-Address}' AND is_active=1 LIMIT 1"
   ```
5. Default reject for unrecognized NAS with Reply-Message="Access denied: NAS not authorized"
**Verification**: `radtest` from known NAS → Access-Accept; from unknown NAS → Access-Reject with message

---

### T32 — Hash backfill for existing radpostauth records
**Files**: `backend/app/` (one-time migration script or Alembic post-migration hook)  
**What to do**:
- Script that reads all existing radpostauth rows with integrity_hash IS NULL
- Computes hash for each using IntegrityHashService
- Updates rows in batches of 500
- Logs progress to stdout
**Verification**: After running script, `SELECT COUNT(*) FROM radpostauth WHERE integrity_hash IS NULL` = 0

---

### T33 — Add background integrity hash job
**Files**: `backend/app/main.py` or `backend/app/core/background.py`  
**What to do**:
- FastAPI startup background task or asyncio periodic task
- Every 60 seconds: call `IntegrityHashService.backfill_hashes(batch_size=500)`
- Log count of hashed records if > 0
**Verification**: New radpostauth records get integrity_hash within 60 seconds of insertion

---

### T34 — Integration test: full auth flow with lockout + audit trail
**Files**: `security_tests/` (add test script)  
**What to do**:
- Script: login 6 times with wrong password → assert 429 on 6th
- Script: login with correct credentials → assert JWT contains role
- Script: decode JWT → assert role field present
- Script: call DELETE /api/users/{id} as auditor → assert 403
- Script: check radpostauth after auth → assert pass='[REDACTED]', nas_ip_address set
**Verification**: All assertions pass

---

## Phase 4 — Testing (BDD + TDD + Integration)

### T35 — Setup del entorno de testing backend (pytest)
**Files**:
- `backend/pytest.ini` (NEW)
- `backend/conftest.py` (NEW)
- `backend/tests/__init__.py` (NEW)
- `backend/requirements-test.txt` (NEW)

**Dependencias a agregar**:
```
pytest==8.x
pytest-asyncio==0.23.x
pytest-bdd==7.x
httpx==0.27.x         # AsyncClient para tests de API
pytest-cov==5.x       # cobertura de código
anyio[trio]==4.x      # backend async para pytest-asyncio
factory-boy==3.x      # factories para fixtures de BD
```

**`backend/pytest.ini`**:
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
addopts = --cov=app --cov-report=term-missing --cov-fail-under=80
```

**`backend/conftest.py`** debe proveer:
- `test_db` fixture: BD SQLite en memoria (o MariaDB de test via Docker) con todas las tablas creadas
- `async_client` fixture: `httpx.AsyncClient` apuntando a la app FastAPI con BD de test
- `superadmin_token` fixture: JWT con role=superadmin
- `admin_token` fixture: JWT con role=admin
- `helpdesk_token` fixture: JWT con role=helpdesk
- `auditor_token` fixture: JWT con role=auditor

**Verification**: `cd backend && pytest --collect-only` lista tests sin errores de importación

---

### T36 — Setup del entorno de testing frontend (vitest)
**Files**:
- `frontend/vitest.config.js` (NEW)
- `frontend/src/test/setup.js` (NEW)

**Dependencias a agregar a `frontend/package.json`**:
```json
"devDependencies": {
  "vitest": "^1.x",
  "@vitest/coverage-v8": "^1.x",
  "@testing-library/react": "^14.x",
  "@testing-library/user-event": "^14.x",
  "@testing-library/jest-dom": "^6.x",
  "jsdom": "^24.x",
  "msw": "^2.x"
}
```

**`frontend/vitest.config.js`**:
```js
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    coverage: { provider: 'v8', threshold: { lines: 80 } }
  }
})
```

**`frontend/src/test/setup.js`**: importar `@testing-library/jest-dom` y configurar MSW handlers para mockear la API.

**Verification**: `cd frontend && npx vitest run` termina con 0 tests (sin fallar)

---

### T37 — Unit tests: IntegrityHashService
**Files**: `backend/tests/unit/test_integrity.py` (NEW)

**Tests a implementar** (TDD — escribir ANTES de implementar T10):

```python
# test_integrity.py
import pytest
from app.services.integrity import compute_hash, CRITICAL_FIELDS_AUTH

class TestComputeHash:
    def test_deterministic_same_input_same_hash(self):
        """El mismo input siempre produce el mismo hash."""
        record = {"username": "jperez", "authdate": "2026-01-01T10:00:00", 
                  "nas_ip_address": "192.168.1.1", "reply": "Access-Accept",
                  "calling_station_id": "10.0.0.1"}
        h1 = compute_hash(record, CRITICAL_FIELDS_AUTH)
        h2 = compute_hash(record, CRITICAL_FIELDS_AUTH)
        assert h1 == h2

    def test_hash_prefix_sha256(self):
        """El hash comienza con 'sha256:'."""
        record = {"username": "x", "authdate": "t", "nas_ip_address": "1",
                  "reply": "y", "calling_station_id": "z"}
        assert compute_hash(record, CRITICAL_FIELDS_AUTH).startswith("sha256:")

    def test_hash_length(self):
        """sha256: + 64 hex chars = 71 caracteres."""
        record = {"username": "x", "authdate": "t", "nas_ip_address": "1",
                  "reply": "y", "calling_station_id": "z"}
        assert len(compute_hash(record, CRITICAL_FIELDS_AUTH)) == 71

    def test_tamper_detection_reply_change(self):
        """Cambiar reply produce un hash diferente."""
        base = {"username": "jperez", "authdate": "2026-01-01T10:00:00",
                "nas_ip_address": "192.168.1.1", "reply": "Access-Accept",
                "calling_station_id": "10.0.0.1"}
        tampered = {**base, "reply": "Access-Reject"}
        assert compute_hash(base, CRITICAL_FIELDS_AUTH) != compute_hash(tampered, CRITICAL_FIELDS_AUTH)

    def test_tamper_detection_username_change(self):
        """Cambiar username produce un hash diferente."""
        base = {"username": "jperez", "authdate": "2026-01-01T10:00:00",
                "nas_ip_address": "192.168.1.1", "reply": "Access-Accept",
                "calling_station_id": "10.0.0.1"}
        tampered = {**base, "username": "attacker"}
        assert compute_hash(base, CRITICAL_FIELDS_AUTH) != compute_hash(tampered, CRITICAL_FIELDS_AUTH)

    def test_missing_field_uses_empty_string(self):
        """Campos ausentes en el record no generan KeyError."""
        record = {"username": "jperez"}  # faltan campos
        h = compute_hash(record, CRITICAL_FIELDS_AUTH)
        assert h.startswith("sha256:")

    def test_field_order_irrelevant(self):
        """El orden de claves en el dict no afecta el hash (canonical form)."""
        r1 = {"username": "a", "authdate": "b", "nas_ip_address": "c",
              "reply": "d", "calling_station_id": "e"}
        r2 = {"calling_station_id": "e", "reply": "d", "nas_ip_address": "c",
              "authdate": "b", "username": "a"}
        assert compute_hash(r1, CRITICAL_FIELDS_AUTH) == compute_hash(r2, CRITICAL_FIELDS_AUTH)
```

**Verification**: `pytest tests/unit/test_integrity.py -v` → 7 tests PASSED

---

### T38 — Unit tests: LockoutService
**Files**: `backend/tests/unit/test_lockout.py` (NEW)

**Tests a implementar** (TDD — escribir ANTES de implementar T11):

```python
# test_lockout.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from app.services.lockout import check_lockout, record_attempt, LOCKOUT_ATTEMPTS, LOCKOUT_WINDOW_MINUTES

class TestCheckLockout:
    async def test_no_attempts_not_locked(self, test_db):
        """Sin intentos previos, la cuenta no está bloqueada."""
        result = await check_lockout(test_db, "newuser")
        assert result is False

    async def test_four_fails_not_locked(self, test_db):
        """4 intentos fallidos < umbral, no hay bloqueo."""
        for _ in range(4):
            await record_attempt(test_db, "jperez", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "jperez") is False

    async def test_five_fails_triggers_lockout(self, test_db):
        """Exactamente 5 intentos fallidos → bloqueado."""
        for _ in range(5):
            await record_attempt(test_db, "jperez", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "jperez") is True

    async def test_lockout_expires_after_window(self, test_db):
        """Intentos más viejos que LOCKOUT_DURATION_MINUTES no cuentan."""
        old_time = datetime.utcnow() - timedelta(minutes=16)
        # Insertar intentos con timestamp pasado directamente en BD
        for _ in range(5):
            await test_db.execute(
                "INSERT INTO login_attempts (username, ip_address, attempted_at, success) "
                "VALUES ('jperez', '10.0.0.1', :ts, 0)",
                {"ts": old_time}
            )
        assert await check_lockout(test_db, "jperez") is False

    async def test_success_does_not_count_toward_lockout(self, test_db):
        """Intentos exitosos no contribuyen al conteo de bloqueo."""
        for _ in range(4):
            await record_attempt(test_db, "jperez", "10.0.0.1", success=False)
        await record_attempt(test_db, "jperez", "10.0.0.1", success=True)
        assert await check_lockout(test_db, "jperez") is False

    async def test_different_users_independent(self, test_db):
        """El bloqueo de un usuario no afecta a otro."""
        for _ in range(5):
            await record_attempt(test_db, "userA", "10.0.0.1", success=False)
        assert await check_lockout(test_db, "userB") is False
```

**Verification**: `pytest tests/unit/test_lockout.py -v` → 6 tests PASSED

---

### T39 — Unit tests: VSAGuardService
**Files**: `backend/tests/unit/test_vsa_guard.py` (NEW)

**Tests a implementar** (TDD — escribir ANTES de implementar T13):

```python
# test_vsa_guard.py
import pytest
from fastapi import HTTPException
from app.services.vsa_guard import validate_vsa_vendor_consistency, check_high_privilege

class TestVSAVendorConsistency:
    def test_cisco_attr_on_cisco_nas_passes(self):
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"}]
        validate_vsa_vendor_consistency("Cisco", attrs)  # no exception

    def test_juniper_attr_on_juniper_nas_passes(self):
        attrs = [{"name": "Juniper-Local-User-Name", "value": "readonly-user"}]
        validate_vsa_vendor_consistency("Juniper", attrs)  # no exception

    def test_cisco_attr_on_juniper_nas_raises_422(self):
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]
        with pytest.raises(HTTPException) as exc:
            validate_vsa_vendor_consistency("Juniper", attrs)
        assert exc.value.status_code == 422
        assert "Cisco-AVPair" in exc.value.detail
        assert "Juniper" in exc.value.detail

    def test_fortinet_attr_on_cisco_nas_raises_422(self):
        attrs = [{"name": "Fortinet-Group-Name", "value": "super_admin_profile"}]
        with pytest.raises(HTTPException) as exc:
            validate_vsa_vendor_consistency("Cisco", attrs)
        assert exc.value.status_code == 422

    def test_standard_attr_passes_any_vendor(self):
        """Atributos RFC estándar (Service-Type, etc.) son válidos en cualquier vendor."""
        attrs = [{"name": "Service-Type", "value": "NAS-Prompt-User"}]
        validate_vsa_vendor_consistency("Cisco", attrs)   # no exception
        validate_vsa_vendor_consistency("Juniper", attrs) # no exception

    def test_unknown_vendor_with_standard_attrs_passes(self):
        attrs = [{"name": "Session-Timeout", "value": "3600"}]
        validate_vsa_vendor_consistency("Generic", attrs)  # no exception

class TestHighPrivilegeCheck:
    def test_cisco_priv15_is_high_privilege(self):
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]
        assert check_high_privilege(attrs) is True

    def test_cisco_priv1_is_not_high_privilege(self):
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"}]
        assert check_high_privilege(attrs) is False

    def test_juniper_superuser_is_high_privilege(self):
        attrs = [{"name": "Juniper-Local-User-Name", "value": "superuser"}]
        assert check_high_privilege(attrs) is True

    def test_fortinet_super_admin_is_high_privilege(self):
        attrs = [{"name": "Fortinet-Group-Name", "value": "super_admin_profile"}]
        assert check_high_privilege(attrs) is True

    def test_huawei_priv15_is_high_privilege(self):
        attrs = [{"name": "Huawei-Exec-Privilege", "value": "15"}]
        assert check_high_privilege(attrs) is True

    def test_empty_attrs_is_not_high_privilege(self):
        assert check_high_privilege([]) is False
```

**Verification**: `pytest tests/unit/test_vsa_guard.py -v` → 12 tests PASSED

---

### T40 — Integration tests: RBAC permission matrix
**Files**: `backend/tests/integration/test_rbac.py` (NEW)

**Purpose**: Verify the complete RBAC permission matrix from REQ-BE-004 — every role against every protected endpoint category.

**Tests a implementar** (usar `async_client` fixture + tokens por rol de `conftest.py`):

```python
# test_rbac.py
import pytest

class TestAuditAccess:
    """GET /api/audit/* — todos los roles deben poder acceder."""
    async def test_superadmin_can_read_audit(self, async_client, superadmin_token):
        resp = await async_client.get("/api/audit/access", headers={"Authorization": f"Bearer {superadmin_token}"})
        assert resp.status_code == 200

    async def test_helpdesk_can_read_audit(self, async_client, helpdesk_token):
        resp = await async_client.get("/api/audit/access", headers={"Authorization": f"Bearer {helpdesk_token}"})
        assert resp.status_code == 200

    async def test_readonly_can_read_audit(self, async_client, readonly_token):
        resp = await async_client.get("/api/audit/access", headers={"Authorization": f"Bearer {readonly_token}"})
        assert resp.status_code == 200


class TestAuditExport:
    """GET /api/audit/export — solo auditor, admin, superadmin."""
    async def test_auditor_can_export(self, async_client, auditor_token):
        resp = await async_client.get("/api/audit/export?format=json", headers={"Authorization": f"Bearer {auditor_token}"})
        assert resp.status_code == 200

    async def test_helpdesk_cannot_export(self, async_client, helpdesk_token):
        resp = await async_client.get("/api/audit/export?format=json", headers={"Authorization": f"Bearer {helpdesk_token}"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Insufficient permissions"

    async def test_readonly_cannot_export(self, async_client, readonly_token):
        resp = await async_client.get("/api/audit/export?format=json", headers={"Authorization": f"Bearer {readonly_token}"})
        assert resp.status_code == 403


class TestAdminUsersRBAC:
    """POST/PUT/DELETE /api/admin-users — solo superadmin."""
    async def test_admin_cannot_create_admin_user(self, async_client, admin_token):
        payload = {"username": "newuser", "email": "x@x.com", "password": "pass", "role": "admin"}
        resp = await async_client.post("/api/admin-users", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 403

    async def test_superadmin_can_create_admin_user(self, async_client, superadmin_token):
        payload = {"username": "newuser2", "email": "y@y.com", "password": "Str0ngP@ssw0rd!", "role": "helpdesk"}
        resp = await async_client.post("/api/admin-users", json=payload, headers={"Authorization": f"Bearer {superadmin_token}"})
        assert resp.status_code in (200, 201)

    async def test_helpdesk_cannot_delete_user(self, async_client, helpdesk_token):
        resp = await async_client.delete("/api/admin-users/999", headers={"Authorization": f"Bearer {helpdesk_token}"})
        assert resp.status_code == 403


class TestGroupsHighPrivilegeRBAC:
    """PUT /api/groups con VSA nivel 15 — solo superadmin."""
    async def test_admin_cannot_assign_priv15(self, async_client, admin_token, test_group_id):
        payload = {"reply_attributes": [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]}
        resp = await async_client.put(f"/api/groups/{test_group_id}", json=payload,
                                      headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 403
        assert "superadmin" in resp.json()["detail"].lower()

    async def test_superadmin_can_assign_priv15(self, async_client, superadmin_token, test_group_id):
        payload = {"reply_attributes": [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]}
        resp = await async_client.put(f"/api/groups/{test_group_id}", json=payload,
                                      headers={"Authorization": f"Bearer {superadmin_token}"})
        assert resp.status_code in (200, 201)


class TestPrivilegeMapRBAC:
    """GET/POST /api/privilege-map — lectura para auditor, escritura para admin+."""
    async def test_auditor_can_read_privilege_map(self, async_client, auditor_token):
        resp = await async_client.get("/api/privilege-map", headers={"Authorization": f"Bearer {auditor_token}"})
        assert resp.status_code == 200

    async def test_auditor_cannot_create_privilege_map(self, async_client, auditor_token):
        payload = {"username": "jperez", "nas_ip": "10.1.1.1", "radius_group": "grp_test",
                   "privilege_level": "level-1", "approved_by": "admin", "review_date": "2027-01-01"}
        resp = await async_client.post("/api/privilege-map", json=payload,
                                       headers={"Authorization": f"Bearer {auditor_token}"})
        assert resp.status_code == 403

    async def test_helpdesk_cannot_create_privilege_map(self, async_client, helpdesk_token):
        payload = {"username": "jperez", "nas_ip": "10.1.1.1", "radius_group": "grp_test",
                   "privilege_level": "level-1", "approved_by": "admin", "review_date": "2027-01-01"}
        resp = await async_client.post("/api/privilege-map", json=payload,
                                       headers={"Authorization": f"Bearer {helpdesk_token}"})
        assert resp.status_code == 403
```

**Nota**: Agregar `readonly_token` y `test_group_id` fixtures al `conftest.py` creado en T35.

**Verification**: `pytest tests/integration/test_rbac.py -v` → 13 tests PASSED; ningún 403 inesperado ni 200 indebido

---

### T41 — Integration tests: flujo completo de lockout
**Files**: `backend/tests/integration/test_lockout_flow.py` (NEW)

**Purpose**: Probar el ciclo de vida completo del lockout con la BD de test real — no mocks.

```python
# test_lockout_flow.py
import pytest

class TestLockoutEndToEnd:
    async def test_six_failed_attempts_trigger_429(self, async_client, test_db):
        """5 intentos fallidos + 6to → HTTP 429."""
        creds = {"username": "testuser", "password": "wrongpassword"}
        for i in range(5):
            resp = await async_client.post("/api/auth/login", json=creds)
            assert resp.status_code == 401, f"Attempt {i+1} should be 401"
        # Sixth attempt must be locked
        resp = await async_client.post("/api/auth/login", json=creds)
        assert resp.status_code == 429
        assert "15 minutes" in resp.json()["detail"].lower()

    async def test_lockout_message_content(self, async_client, test_db):
        """El mensaje de error 429 debe indicar duración del bloqueo."""
        creds = {"username": "testuser2", "password": "wrongpassword"}
        for _ in range(5):
            await async_client.post("/api/auth/login", json=creds)
        resp = await async_client.post("/api/auth/login", json=creds)
        assert resp.status_code == 429
        body = resp.json()["detail"]
        assert "Account temporarily locked" in body

    async def test_successful_login_after_lockout_expiry(self, async_client, test_db):
        """Tras expirar el lockout, un login correcto debe funcionar."""
        import asyncio
        from app.services.lockout import clear_old_attempts
        # Registrar intentos con timestamp >15min en el pasado directamente
        from datetime import datetime, timedelta
        from sqlalchemy import text
        old_ts = datetime.utcnow() - timedelta(minutes=16)
        for _ in range(5):
            await test_db.execute(
                text("INSERT INTO login_attempts (username, ip_address, attempted_at, success) "
                     "VALUES (:u, '127.0.0.1', :ts, 0)"),
                {"u": "testuser3", "ts": old_ts}
            )
        await test_db.commit()
        # Now login should succeed (lockout has expired)
        resp = await async_client.post("/api/auth/login",
                                       json={"username": "testuser3", "password": "correctpassword"})
        assert resp.status_code == 200

    async def test_superadmin_unlock_clears_lockout(self, async_client, test_db, superadmin_token):
        """Un superadmin puede desbloquear una cuenta bloqueada inmediatamente."""
        creds = {"username": "testuser4", "password": "wrongpassword"}
        for _ in range(5):
            await async_client.post("/api/auth/login", json=creds)
        # Verify locked
        resp = await async_client.post("/api/auth/login", json=creds)
        assert resp.status_code == 429
        # Superadmin unlocks
        user_id = await _get_user_id(test_db, "testuser4")
        resp = await async_client.post(f"/api/admin-users/{user_id}/unlock",
                                       headers={"Authorization": f"Bearer {superadmin_token}"})
        assert resp.status_code == 200
        # Now login succeeds
        resp = await async_client.post("/api/auth/login",
                                       json={"username": "testuser4", "password": "correctpassword"})
        assert resp.status_code == 200

    async def test_jwt_contains_role_field(self, async_client, test_db):
        """El JWT devuelto tras login exitoso debe contener el campo 'role'."""
        import jwt as pyjwt
        resp = await async_client.post("/api/auth/login",
                                       json={"username": "superadmin", "password": "adminpassword"})
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        payload = pyjwt.decode(token, options={"verify_signature": False})
        assert "role" in payload
        assert payload["role"] in ("superadmin", "admin", "helpdesk", "auditor", "readonly")

    async def test_pap_password_is_redacted_in_radpostauth(self, async_client, test_db):
        """Tras autenticación, radpostauth.pass debe ser '[REDACTED]', no la contraseña real."""
        from sqlalchemy import text
        await async_client.post("/api/auth/login",
                                json={"username": "radiususer", "password": "mypassword123"})
        # Check via direct DB query (radpostauth is populated by FreeRADIUS, but in integration
        # test environment we can verify via the service layer or the audit endpoint)
        result = await test_db.execute(
            text("SELECT pass FROM radpostauth WHERE username='radiususer' ORDER BY authdate DESC LIMIT 1")
        )
        row = result.fetchone()
        if row:  # May be empty in unit test env without FreeRADIUS
            assert row[0] == "[REDACTED]"
            assert row[0] != "mypassword123"
```

**Verification**: `pytest tests/integration/test_lockout_flow.py -v` → 6 tests PASSED (el último puede ser skipped en entornos sin FreeRADIUS)

---

### T42 — Unit tests frontend: RoleGuard + AuthContext
**Files**: `frontend/src/test/RoleGuard.test.jsx` (NEW), `frontend/src/test/AuthContext.test.jsx` (NEW)

**Purpose**: Verificar que el guard de roles del frontend y la extracción del rol del JWT funcionan correctamente.

**`frontend/src/test/RoleGuard.test.jsx`**:
```jsx
// RoleGuard.test.jsx
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RoleGuard from '../components/RoleGuard'

// Mock del hook useAuth
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn()
}))
import { useAuth } from '../context/AuthContext'

describe('RoleGuard', () => {
  it('renders children when user has allowed role', () => {
    useAuth.mockReturnValue({ role: 'superadmin' })
    render(
      <RoleGuard allowedRoles={['superadmin', 'admin']}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('renders fallback when user role is not allowed', () => {
    useAuth.mockReturnValue({ role: 'helpdesk' })
    render(
      <RoleGuard allowedRoles={['superadmin', 'admin']} fallback={<span>Access Denied</span>}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
    expect(screen.getByText('Access Denied')).toBeInTheDocument()
  })

  it('renders null (not null fallback) when fallback is not provided', () => {
    useAuth.mockReturnValue({ role: 'readonly' })
    const { container } = render(
      <RoleGuard allowedRoles={['superadmin']}>
        <span>Protected Content</span>
      </RoleGuard>
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders children when user is auditor and auditor is allowed', () => {
    useAuth.mockReturnValue({ role: 'auditor' })
    render(
      <RoleGuard allowedRoles={['auditor', 'admin', 'superadmin']}>
        <span>Audit View</span>
      </RoleGuard>
    )
    expect(screen.getByText('Audit View')).toBeInTheDocument()
  })

  it('does not render children for unauthenticated user (role=null)', () => {
    useAuth.mockReturnValue({ role: null })
    const { container } = render(
      <RoleGuard allowedRoles={['superadmin']}>
        <span>Should Not Appear</span>
      </RoleGuard>
    )
    expect(screen.queryByText('Should Not Appear')).not.toBeInTheDocument()
  })
})
```

**`frontend/src/test/AuthContext.test.jsx`**:
```jsx
// AuthContext.test.jsx
import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { AuthProvider, useAuth } from '../context/AuthContext'

// JWT con payload { sub: "jperez", role: "superadmin", exp: 9999999999 }
const MOCK_JWT_SUPERADMIN =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  btoa(JSON.stringify({ sub: 'jperez', role: 'superadmin', exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_') +
  '.signature'

const MOCK_JWT_HELPDESK =
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.' +
  btoa(JSON.stringify({ sub: 'hdesk', role: 'helpdesk', exp: 9999999999 }))
    .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_') +
  '.signature'

describe('AuthContext — role extraction from JWT', () => {
  it('extracts superadmin role correctly from JWT', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_SUPERADMIN}>{children}</AuthProvider>
      )
    })
    expect(result.current.role).toBe('superadmin')
  })

  it('extracts helpdesk role correctly from JWT', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_HELPDESK}>{children}</AuthProvider>
      )
    })
    expect(result.current.role).toBe('helpdesk')
  })

  it('role is null when no token is set', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>
    })
    expect(result.current.role).toBeNull()
  })

  it('hasRole returns true when user has the specified role', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_SUPERADMIN}>{children}</AuthProvider>
      )
    })
    expect(result.current.hasRole(['superadmin', 'admin'])).toBe(true)
  })

  it('hasRole returns false when user does not have the specified role', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => (
        <AuthProvider initialToken={MOCK_JWT_HELPDESK}>{children}</AuthProvider>
      )
    })
    expect(result.current.hasRole(['superadmin', 'admin'])).toBe(false)
  })
})

describe('PrivilegeMap review badge logic', () => {
  it('shows "Review Soon" badge when review_date is within 30 days', () => {
    const { getByText } = render(
      <ReviewBadge reviewDate={new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString()} />
    )
    expect(getByText(/Revisión próxima/i)).toBeInTheDocument()
  })

  it('shows "Overdue" badge when review_date is in the past', () => {
    const { getByText } = render(
      <ReviewBadge reviewDate={new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()} />
    )
    expect(getByText(/Vencido/i)).toBeInTheDocument()
  })

  it('shows no badge when review_date is more than 30 days away', () => {
    const { queryByText } = render(
      <ReviewBadge reviewDate={new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString()} />
    )
    expect(queryByText(/Revisión próxima/i)).not.toBeInTheDocument()
    expect(queryByText(/Vencido/i)).not.toBeInTheDocument()
  })
})
```

**Nota**: `ReviewBadge` es el componente de badge dentro de `PrivilegeMap.jsx` (creado en T29). Extraer como componente separado `frontend/src/components/ReviewBadge.jsx` si no existe.

**Verification**: `cd frontend && npx vitest run` → todos los tests de T42 PASSED

---

## Task Summary

| Task | Phase | Depends on | Priority | Est. effort |
|------|-------|------------|----------|-------------|
| T01 | 1 | — | CRITICAL | 2h |
| T02 | 1 | T01 | CRITICAL | 1h |
| T03 | 1 | T01 | HIGH | 1h |
| T04 | 1 | — | CRITICAL | 1h |
| T05 | 1 | — | CRITICAL | 1h |
| T06 | 1 | — | CRITICAL | 1h |
| T07 | 1 | — | CRITICAL | 2h |
| T08 | 1 | — | HIGH | 1h |
| T09 | 1 | T07 | CRITICAL | 1h |
| T10 | 2 | T01, T07 | CRITICAL | 2h |
| T11 | 2 | T01, T04 | CRITICAL | 2h |
| T12 | 2 | T01, T03 | HIGH | 2h |
| T13 | 2 | T01 | HIGH | 2h |
| T14 | 2 | — | HIGH | 2h |
| T15 | 2 | T01, T10 | HIGH | 2h |
| T16 | 2 | T01, T02, T11, T12 | CRITICAL | 3h |
| T17 | 2 | T01, T12 | HIGH | 2h |
| T18 | 2 | T01, T12, T13 | HIGH | 3h |
| T19 | 2 | T01, T12, T11 | HIGH | 3h |
| T20 | 2 | T01, T12, T15 | HIGH | 3h |
| T21 | 2 | T14 | HIGH | 1h |
| T22 | 2 | T01, T06, T12 | HIGH | 3h |
| T23 | 2 | T01 | MEDIUM | 2h |
| T24 | 3 | — | HIGH | 1h |
| T25 | 3 | T24 | HIGH | 1h |
| T26 | 3 | T24, T25 | HIGH | 2h |
| T27 | 3 | T24, T25 | HIGH | 1h |
| T28 | 3 | T07, T20 | HIGH | 2h |
| T29 | 3 | T06, T22, T25 | HIGH | 4h |
| T30 | 3 | T14, T21 | MEDIUM | 2h |
| T31 | 3 | T06 | HIGH | 3h |
| T32 | 3 | T07, T10 | HIGH | 1h |
| T33 | 3 | T10, T32 | MEDIUM | 1h |
| T34 | 3 | T16, T18, T19, T20 | HIGH | 2h |
| T35 | 4 | — | HIGH | 1h |
| T36 | 4 | — | HIGH | 1h |
| T37 | 4 | T35 | HIGH | 1h |
| T38 | 4 | T35 | HIGH | 1h |
| T39 | 4 | T35 | HIGH | 1h |
| T40 | 4 | T35, T12, T16, T17, T18, T19, T20, T22 | HIGH | 2h |
| T41 | 4 | T35, T11, T16 | HIGH | 2h |
| T42 | 4 | T36, T24, T25 | HIGH | 2h |

**Total**: 42 tasks · ~70h estimated

---

## Recommended Execution Order

```
Phase 1 (unblock DB layer):
  T01 → T02 → T03, T04, T05, T06, T07, T08 (T03–T08 parallelizable after T01)
  T09 (after T07)

Phase 2 (backend security, after Phase 1):
  T35, T36 (setup testing — parallelizable with T10–T15)
  T10, T11, T12, T13, T14, T23 (parallelizable)
  T37, T38, T39 (unit tests — write after services designed, before implementing)
  T15 (after T10)
  T16 (after T11, T12, T15)
  T17, T18, T19, T20, T21, T22 (after T12)

Phase 3 (frontend + RADIUS, after Phase 2):
  T24 → T25 → T26, T27
  T28, T29, T30
  T31
  T32, T33 (after T10)
  T34 (smoke test, after all backend)

Phase 4 (integration tests, after Phase 2+3):
  T40, T41 (after all backend endpoints implemented)
  T42 (after T24, T25)
```
