# Design: iso27001-compliance-improvements
**Change**: ISO/IEC 27001:2022 Compliance Improvements  
**Project**: RADIUS-gestor  
**Date**: 2026-03-14  

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                          │
│  Audit Page (enhanced) │ Privilege Map Page (new) │ RBAC menus  │
└────────────────┬────────────────────────────────────────────────┘
                 │ REST (JWT + role claim)
┌────────────────▼────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ RBAC Depend. │  │ AuditService │  │  IntegrityHashService│  │
│  │ (new)        │  │ (enhanced)   │  │  (new)               │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ LockoutService│  │ VSAGuardSvc │  │  NTPStatusService    │  │
│  │ (new)        │  │ (new)        │  │  (new)               │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  Routers: auth | users | nas | groups | audit | privilege_map   │
└────────────────┬────────────────────────────────────────────────┘
                 │ SQLAlchemy async
┌────────────────▼────────────────────────────────────────────────┐
│                     DATABASE (MariaDB 10.11)                     │
│                                                                  │
│  radpostauth (enhanced) │ radacct (enhanced)                     │
│  radius_reply_audit (NEW) │ user_nas_privilege_map (NEW)         │
│  login_attempts (NEW) │ admin_users (role column added)          │
└─────────────────────────────────────────────────────────────────┘
                 │ SQL queries
┌────────────────▼────────────────────────────────────────────────┐
│                  FREERADIUS (Docker container)                   │
│                                                                  │
│  radius/sql (fixed postauth_query)                               │
│  radius/policy.d/nas_based_authorization (NEW unlang policy)     │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Map

### New Files
```
backend/app/
├── services/
│   ├── integrity.py          # SHA-256 hash service
│   ├── lockout.py            # Account lockout logic
│   ├── vsa_guard.py          # VSA vendor consistency guard
│   └── ntp_status.py         # NTP sync checker (calls chronyc/ntpq)
├── routers/
│   └── privilege_map.py      # CRUD for user_nas_privilege_map
├── core/
│   └── rbac.py               # Role enum + FastAPI dependencies
└── models/
    └── (additions to models.py for new tables)

database/migrations/
├── 001_radpostauth_enhance.sql
├── 002_radacct_enhance.sql
├── 003_new_tables.sql
└── 004_admin_users_role.sql

radius/
└── policy.d/
    └── nas_based_authorization   # FreeRADIUS unlang policy

frontend/src/
├── pages/
│   └── PrivilegeMap.jsx          # New privilege mapping page
└── context/
    └── (role-aware updates to AuthContext)
```

### Modified Files
```
database/init.sql                           # Add new tables + ALTER stmts
radius/sql                                  # Fix postauth_query
backend/app/models/models.py                # Add new models + fix LSP errors
backend/app/schemas/schemas.py              # Add new schemas
backend/app/services/audit.py               # Add event codes + hash integration
backend/app/routers/auth.py                 # Add lockout + ADMIN-007 + fix LSP
backend/app/routers/nas.py                  # Add secret length validation + ADMIN-009
backend/app/routers/groups.py               # Add VSA guard + high-priv guard + fix LSP
backend/app/routers/audit.py                # Add SIEM export endpoint
backend/app/routers/admin_users.py          # Add role management + fix LSP
backend/app/core/security.py                # Add role to JWT + fix LSP errors
backend/app/main.py                         # Register new router + fix LSP
frontend/src/pages/Audit.jsx                # Add NAS IP + calling_station columns
frontend/src/App.jsx (or Router)            # Add /privilege-map route + role guards
frontend/src/context/AuthContext.jsx        # Expose role from JWT
```

---

## Data Flow

### 1. Authentication Flow (enhanced)

```
Client → POST /api/auth/login
  │
  ├─ LockoutService.check(username, ip) ──→ if locked: return 429
  │
  ├─ verify_password(plain, hashed)
  │   ├─ FAIL → LockoutService.record_fail(username, ip)
  │   │          if attempts >= 5 in 10min → auto-lock for 15min
  │   │          AuditService.log(AUTH-004, username)
  │   │          return 401
  │   │
  │   └─ SUCCESS → LockoutService.record_success(username, ip)
  │                 AuditService.log(ADMIN-007, username, ip)
  │                 return JWT with {sub, role, exp}
```

### 2. Integrity Hash Flow

```
FreeRADIUS INSERT into radpostauth (via radius/sql)
  │  (nas_ip_address, calling_station_id now included)
  │  (pass = '[REDACTED]')
  │
  └─→ Backend periodic job OR trigger-based:
       IntegrityService.compute_hash(record)
         fields = [username, authdate, nas_ip_address, reply, calling_station_id]
         canonical = json.dumps(sorted_dict, sort_keys=True)
         hash = "sha256:" + sha256(canonical).hexdigest()
       UPDATE radpostauth SET integrity_hash=hash WHERE id=?

Note: FreeRADIUS inserts directly; hash can be computed by backend
on read (lazy) or via a scheduled job (eager). Eager preferred for A.5.33.
```

### 3. RBAC Flow

```
Request → JWT decode → extract role
  │
  ├─ require_role(["superadmin","admin"]) dependency
  │   └─ if role not in allowed_roles → raise 403
  │
  └─ Role-specific logic (e.g., VSA high-priv guard checks role==superadmin)
```

### 4. SIEM Export Flow

```
GET /api/audit/export?format=json&from=T1&to=T2
  │
  ├─ RBAC check (auditor/admin/superadmin only)
  │
  ├─ Query radpostauth JOIN NAS data WHERE authdate BETWEEN T1 AND T2
  │
  ├─ For each record: build SIEMEvent schema
  │   (includes ntp_synchronized from NTPStatusService cached value)
  │
  ├─ Log ADMIN-008 event
  │
  └─ Return StreamingResponse (JSON array) or FileResponse (CSV)
```

---

## Key Design Decisions

### Decision 1: Hash computation — eager vs lazy
**Choice**: Eager (background job every 60s)  
**Why**: Lazy hash on read defeats tampering detection (attacker modifies record AND we only detect on next read). Eager job runs `UPDATE radpostauth SET integrity_hash=... WHERE integrity_hash IS NULL` periodically.  
**Alternative considered**: DB trigger — rejected because MariaDB triggers can't use Python's json.dumps canonical form easily.

### Decision 2: Role storage — JWT claim vs DB lookup
**Choice**: JWT claim (`role` in payload)  
**Why**: Avoids DB round-trip on every request. Role changes take effect on next login (token expiry). Acceptable trade-off.  
**Risk**: Role escalation after revoke requires token invalidation. Mitigated by short token TTL (1h) + logout-on-role-change flow.

### Decision 3: Lockout storage — DB vs Redis
**Choice**: DB (login_attempts table in MariaDB)  
**Why**: No Redis in current stack. login_attempts table with TTL-based query (WHERE attempted_at > NOW() - INTERVAL 10 MINUTE) is fast enough for this scale.  
**Cleanup**: Cron or background task deletes rows older than 24h.

### Decision 4: FreeRADIUS policy — shadow vs enforce
**Choice**: Implement in enforce mode but with comprehensive logging first  
**Why**: Shadow mode requires dual-policy complexity. Instead, populate user_nas_privilege_map before enabling unlang, and test with `radtest` per NAS before deploying.

### Decision 5: Fix preexisting LSP errors
**Discovery**: Multiple files have SQLAlchemy Column type errors (accessing `.Column[str]` where `str` is expected). Root cause: models use `Column(String)` without `Mapped[]` annotations (SQLAlchemy 1.x style with 2.x).  
**Fix**: Update model attributes to use `Mapped[str]`, `Mapped[int]` etc. This is a prerequisite for the RBAC work since we add `role` to AdminUser.

---

## LSP Errors to Fix (preexisting)

### backend/app/models/models.py
Convert all `Column(Type)` declarations to `Mapped[type] = mapped_column(Type)` style (SQLAlchemy 2.x).

### backend/app/core/security.py:45,58
- Line 45: `payload.get("sub")` returns `Any | None` → add `or ""` default
- Line 58: `Column[int]` boolean comparison → access `.is_(True)` or cast to int

### backend/app/routers/admin_users.py, auth.py, groups.py
All errors stem from SQLAlchemy model columns being `Column[str]` instead of `Mapped[str]`. Fixed by fixing models.py first.

### backend/app/main.py:33
`Session` vs `AsyncSession` — verify `get_db()` returns `AsyncSession` properly.

---

## New Service Interfaces

### `backend/app/services/integrity.py`
```python
CRITICAL_FIELDS_AUTH = ["username", "authdate", "nas_ip_address", "reply", "calling_station_id"]

def compute_hash(record: dict, fields: list[str]) -> str:
    canonical = {k: str(record.get(k, "")) for k in sorted(fields)}
    payload = json.dumps(canonical, ensure_ascii=True, sort_keys=True)
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()

async def verify_record_integrity(db: AsyncSession, record_id: int) -> bool: ...
async def backfill_missing_hashes(db: AsyncSession, batch_size: int = 500) -> int: ...
```

### `backend/app/services/lockout.py`
```python
LOCKOUT_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 10
LOCKOUT_DURATION_MINUTES = 15

async def check_lockout(db: AsyncSession, username: str) -> bool: ...
async def record_attempt(db: AsyncSession, username: str, ip: str, success: bool) -> None: ...
async def unlock_user(db: AsyncSession, username: str) -> None: ...
```

### `backend/app/services/vsa_guard.py`
```python
VENDOR_ATTRIBUTE_MAP = {
    "Cisco": ["Cisco-AVPair"],
    "Juniper": ["Juniper-Local-User-Name"],
    "Fortinet": ["Fortinet-Group-Name", "Fortinet-Vdom-Name"],
    "Huawei": ["Huawei-Exec-Privilege"],
}
HIGH_PRIVILEGE_ATTRS = {
    "Cisco-AVPair": ["shell:priv-lvl=15", "shell:roles=\"network-admin\""],
    "Juniper-Local-User-Name": ["superuser"],
    "Fortinet-Group-Name": ["super_admin_profile"],
    "Huawei-Exec-Privilege": ["15"],
}

def validate_vsa_vendor_consistency(nas_vendor: str, attributes: list[dict]) -> None: ...
def check_high_privilege(attributes: list[dict]) -> bool: ...
```

### `backend/app/core/rbac.py`
```python
class Role(str, Enum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    HELPDESK = "helpdesk"
    AUDITOR = "auditor"
    READONLY = "readonly"

def require_roles(*roles: Role) -> Depends:
    """FastAPI dependency factory for role-based access control."""
    async def check(current_user = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return Depends(check)
```

---

## Database Migration Strategy

All changes delivered as SQL migration files (also as Alembic scripts):

1. **001_radpostauth_enhance.sql** — ALTER + backfill integrity_hash=NULL (FreeRADIUS keeps working with DEFAULT values)
2. **002_radacct_enhance.sql** — ALTER for new accounting fields  
3. **003_new_tables.sql** — CREATE radius_reply_audit, user_nas_privilege_map, login_attempts
4. **004_admin_users_role.sql** — ALTER admin_users ADD role + UPDATE SET role='superadmin' WHERE id=(SELECT MIN(id)...)

Migrations are additive (no DROP, no NOT NULL without DEFAULT). Safe to run on live system with brief maintenance window.

---

## FreeRADIUS Policy Design

### `radius/policy.d/nas_based_authorization`
```unlang
nas_based_authorization {
    # Require NAS IP or Identifier to be present
    if (!(&NAS-IP-Address || &NAS-Identifier)) {
        update reply { Reply-Message := "Access denied: NAS identification missing" }
        reject
    }

    # Map NAS IP to RADIUS group via user_nas_privilege_map table
    # FreeRADIUS queries DB for group assignment
    if (&NAS-IP-Address) {
        update control {
            # SQL lookup: SELECT radius_group FROM user_nas_privilege_map
            # WHERE username='%{User-Name}' AND nas_ip='%{NAS-IP-Address}' AND is_active=1
        }
    }

    # Default: reject if no mapping found
    if (!&control:Ldap-Group) {
        update reply { Reply-Message := "Access denied: NAS not authorized" }
        reject
    }
}
```

Policy is included in `sites-enabled/default` authorize section after sql module.

---

## Frontend Component Design

### PrivilegeMap.jsx (new page)
```
<PrivilegeMapPage>
  <PageHeader title="Privilege Mapping" subtitle="user-NAS-privilege assignments" />
  <FilterBar fields=[username, nas_ip, vendor, review_status] />
  <DataTable
    columns=[Username, NAS IP, NAS ID, Vendor, Group, Priv Level, Review Date, Status, Actions]
    rowBadge: review_date within 30 days → "Review Soon" (yellow)
    rowBadge: review_date passed → "Overdue" (red)
  />
  <Modal type="create/edit" fields=[username, nas_ip, nas_vendor, radius_group, 
                                     privilege_level, justification, approved_by, review_date] />
</PrivilegeMapPage>
```

### Audit.jsx (enhanced)
New columns in access log tab:
- **NAS IP** (nas_ip_address)
- **NAS ID** (nas_identifier)  
- **Calling Station** (calling_station_id)
- **Event Code** (event_source + derived code)
New filter: NAS IP filter input

### AuthContext.jsx / JWT decoding
Extract `role` from JWT payload. Expose as `currentUser.role`.

### Role-gated routing
```jsx
<RoleGuard allowedRoles={["superadmin", "admin"]}>
  <Route path="/privilege-map" element={<PrivilegeMap />} />
</RoleGuard>
```
