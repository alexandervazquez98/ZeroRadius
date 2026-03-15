# Proposal: ISO 27001 Compliance Improvements

**Change**: iso27001-compliance-improvements
**Date**: 2026-03-14
**Session**: sdd-improve-radius-gestor-2026-03-14
**Status**: Draft

---

## Intent

RADIUS-gestor manages network access control for an organization's infrastructure. As the central authority for 802.1X/RADIUS authentication, it falls within scope of ISO 27001 controls A.5.17 (credentials), A.5.18 (access rights), A.5.33 (audit log integrity), A.8.2 (privileged access), A.8.3 (access restriction), A.8.15 (logging), A.8.16 (monitoring), and A.8.17 (clock synchronization).

A gap analysis identified **6 critical** and **12 high-priority** compliance deficiencies:

- PAP passwords are stored in plain text in `radpostauth` — a direct credential exposure risk.
- Audit records lack integrity hashes and are mutable, violating tamper-evidence requirements.
- No account lockout exposes the admin console to brute-force attacks.
- Missing database tables and schema fields make forensic reconstruction impossible.
- No role separation means all admins have full access (no segregation of duties).
- FreeRADIUS grants access without per-NAS policy — any valid credential authenticates from any NAS.

This change implements a **3-phase compliance initiative** to address all 18 identified gaps and bring RADIUS-gestor to a defensible ISO 27001 posture.

---

## Scope

### In Scope

**Phase 1 — Database & RADIUS Layer (CRÍTICA)**
- Expand `radpostauth` with forensic NAS fields (nas_ip_address, calling_station_id, nas_identifier, reply_message, event_source, integrity_hash)
- Expand `radacct` with missing compliance fields (nasidentifier, privilege_level, vendor_reply_attrs)
- Remove `ON UPDATE CURRENT_TIMESTAMP` from `authdate` column
- Create `radius_reply_audit` table for reply attribute logging
- Create `user_nas_privilege_map` table for per-user NAS privilege assignments
- Create `login_attempts` table for account lockout tracking
- Add `role` column to `admin_users` table
- Remove PAP password from FreeRADIUS `radpostauth` SQL logging query (`radius/sql`)

**Phase 2 — Backend Security Layer (ALTA)**
- SHA-256 integrity hash service (chained hashes per audit record)
- Structured event code enum (AUTH-001..007, ACCT-001..004, ADMIN-001..009)
- Account lockout mechanism (5 failures → 15-minute lockout, ADMIN-008/009 events)
- Role-based access control (superadmin / admin / helpdesk / auditor) for all endpoints
- SIEM JSON export endpoint (`GET /audit/export`)
- NAS secret minimum length validation (≥ 32 chars, Pydantic validator)
- VSA consistency guard (vendor ↔ attribute ID whitelist)
- High-privilege VSA guard (superadmin-only for flagged VSAs)
- ADMIN-007 event emitted on every successful admin login

**Phase 3 — Frontend & RADIUS Policy (ALTA)**
- Enhanced Audit page: NAS IP + calling_station_id columns
- New Privilege Mapping page: CRUD for `user_nas_privilege_map`
- Role-based UI visibility (menu items, action buttons gated by role)
- FreeRADIUS NAS-conditional authorization policy (unlang, checks `user_nas_privilege_map`)
- NTP sync status backend endpoint + UI indicator in dashboard header

### Out of Scope

- Full PKI / certificate-based EAP (EAP-TLS) — separate initiative
- RADIUS accounting policy enforcement beyond schema additions
- Automated ISO 27001 audit report generation
- Integration with external SIEM platforms (only the export endpoint; ingestion side is out of scope)
- Password rotation policies for end-user RADIUS accounts (outside admin scope)
- Two-factor authentication for admin console (deferred)

---

## Approach

### Phase 1: Database & RADIUS Foundation

All schema changes are delivered as Alembic migrations. The migration strategy is additive (new columns, new tables) to minimize disruption to existing data. The one destructive change — removing `ON UPDATE` from `authdate` — is safe via `ALTER TABLE MODIFY COLUMN`.

FreeRADIUS `radius/sql` postauth query is modified to exclude the `User-Password` attribute from the `reply` column via a `%{if}` conditional or by rewriting the column mapping.

No application code changes in Phase 1 — this is schema-only groundwork.

### Phase 2: Backend Hardening

All changes are implemented in the FastAPI backend without breaking existing API contracts:

- **Integrity hashes**: A new `HashService` computes `SHA-256(event_code || actor_id || target || utc_timestamp || prev_hash)`. The genesis hash is SHA-256 of a fixed seed. All `audit_service.log()` calls are updated to call `HashService.compute_and_chain()`.
- **Event codes**: A Python `EventCode` enum replaces free-text event descriptions. Existing `ADMIN-001..005` events are mapped; new codes added.
- **Account lockout**: A `LoginAttemptService` checks `login_attempts` before authentication and records failures. On 5th failure within 15 minutes, sets `locked_until` timestamp. Admin unlock via `POST /admin/{id}/unlock` (superadmin only).
- **RBAC**: A `require_role(*roles)` FastAPI dependency replaces `get_current_admin`. All existing endpoints annotated with required role. New role hierarchy: `superadmin > admin > helpdesk > auditor`.
- **SIEM export**: New router `audit_export.py` with `GET /audit/export` accepting `format` (json/csv), `from`, `to`, `event_codes[]` query params. Returns NDJSON stream or CSV file download.
- **NAS secret validation**: Pydantic `NasCreate`/`NasUpdate` schema updated with `@validator('secret')` enforcing `len >= 32`.
- **VSA guards**: `GroupsRouter` updated with a `VSA_VENDOR_ATTR_MAP` whitelist and a `HIGH_PRIVILEGE_VSAS` set. Violations return HTTP 422.

### Phase 3: Frontend & FreeRADIUS Policy

Frontend changes use the existing React/TanStack Query/Tailwind stack:

- **Audit page**: Add two new columns to the `<AuditTable>` component; update TanStack Query fetch to include new fields.
- **Privilege Mapping page**: New route `/privilege-map`; CRUD page following the pattern of existing NAS/Groups pages.
- **Role-based UI**: Auth context enriched with `role`; `<RoleGuard role="admin">` wrapper component gates menu items and action buttons.
- **NTP indicator**: New `useNtpStatus` hook polls `GET /system/ntp-status`; renders a clock icon with color indicator in the top nav.

FreeRADIUS unlang policy added to `radius/policy.d/` and referenced from `sites-available/default`. The policy queries `user_nas_privilege_map` via SQL on every `authorize` request.

---

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `database/init.sql` | Modified | Schema additions: columns + 3 new tables |
| `database/migrations/` | New | Alembic migration files for all schema changes |
| `radius/sql` | Modified | Remove PAP password from postauth query |
| `radius/policy.d/nas-conditional-authz.policy` | New | FreeRADIUS NAS-conditional authorization |
| `radius/sites-available/default` | Modified | Reference new policy file |
| `backend/app/services/audit.py` | Modified | Add hash chaining, event codes |
| `backend/app/services/hash_service.py` | New | SHA-256 hash chain implementation |
| `backend/app/services/lockout_service.py` | New | Login attempt tracking and lockout |
| `backend/app/core/security.py` | Modified | Add role support, `require_role()` dependency |
| `backend/app/models/admin.py` | Modified | Add `role` field to `AdminUser` |
| `backend/app/models/lockout.py` | New | `LoginAttempt` SQLAlchemy model |
| `backend/app/models/privilege_map.py` | New | `UserNasPrivilegeMap` SQLAlchemy model |
| `backend/app/routers/auth.py` | Modified | Integrate lockout, emit ADMIN-007 event |
| `backend/app/routers/nas.py` | Modified | Add secret length validator |
| `backend/app/routers/groups.py` | Modified | VSA consistency + privilege guards |
| `backend/app/routers/audit.py` | Modified | Add SIEM export endpoint |
| `backend/app/routers/privilege_map.py` | New | CRUD for user_nas_privilege_map |
| `backend/app/routers/system.py` | New | NTP status endpoint |
| `frontend/src/pages/Audit.jsx` | Modified | Add NAS IP + calling_station columns |
| `frontend/src/pages/PrivilegeMap.jsx` | New | User-NAS privilege mapping CRUD page |
| `frontend/src/components/RoleGuard.jsx` | New | Role-based rendering component |
| `frontend/src/components/NtpStatus.jsx` | New | NTP sync indicator |
| `frontend/src/context/AuthContext.jsx` | Modified | Enrich with role field |
| `frontend/src/App.jsx` | Modified | Add `/privilege-map` route |
| `frontend/src/components/Sidebar.jsx` | Modified | Role-gated menu items |

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Alembic migration fails on existing production data | Low | High | Test migration on a staging DB dump before applying to production. Provide rollback SQL. |
| FreeRADIUS policy rejects legitimate authentications | Medium | High | Test unlang policy in shadow mode (policy logs but does not reject) before enforcing. |
| Role assignment leaves admins locked out | Medium | High | Migration sets `role = 'superadmin'` for the first admin user and `role = 'admin'` for all others. Document manual recovery via DB. |
| Hash chain corruption if audit service crashes mid-write | Low | Medium | Store `prev_hash` atomically with the audit record in a transaction. On service restart, resume from last written hash. |
| VSA whitelist too restrictive, breaks existing groups | Medium | Medium | Audit all existing VSA configurations before enabling strict validation; run in warn-only mode first. |
| NTP endpoint exposes infrastructure timing data | Low | Low | Endpoint returns only `synced: bool` and `offset_ms: int`; no server hostnames exposed. |

---

## Rollback Plan

**Phase 1 (Database)**:
- Each Alembic migration has a corresponding `downgrade()` function. Run `alembic downgrade -1` per migration.
- FreeRADIUS `radius/sql` change: restore previous postauth query from git. Restart FreeRADIUS container.

**Phase 2 (Backend)**:
- All backend changes are additive or replace existing behavior. Roll back via `git revert` of the relevant commit.
- If RBAC breaks admin access: connect directly to DB and set `role = 'superadmin'` for affected user.

**Phase 3 (Frontend + RADIUS policy)**:
- Frontend: `git revert` + Vite rebuild.
- FreeRADIUS policy: remove `nas-conditional-authz.policy` reference from `sites-available/default` and restart container.

**Full rollback order**: Phase 3 → Phase 2 → Phase 1 (reverse order to maintain consistency).

---

## Dependencies

- MariaDB 10.11+ with `ALTER TABLE` support for the specific column type changes (verified compatible).
- FreeRADIUS 3.x with `rlm_sql` module enabled (already in Docker setup).
- Python `hashlib` (stdlib — no new dependency for SHA-256).
- Alembic already installed as project dependency.
- No new npm packages required for frontend changes (Lucide icons already available for NTP indicator).

---

## Success Criteria

### Phase 1
- [ ] `radpostauth` contains no `User-Password` values in any new records after migration + FreeRADIUS restart
- [ ] `radpostauth` schema contains all 6 new forensic columns
- [ ] `radacct` schema contains all 3 new columns
- [ ] `authdate` column has no `ON UPDATE` clause (verified via `SHOW CREATE TABLE`)
- [ ] `radius_reply_audit` table exists and is populated on authentication events
- [ ] `user_nas_privilege_map` table exists with correct FK constraints
- [ ] `login_attempts` table exists
- [ ] `admin_users.role` column exists with default `admin`

### Phase 2
- [ ] All audit records include a non-null `integrity_hash` field
- [ ] Hash chain is verifiable: re-computing hash from record fields matches stored hash
- [ ] Admin account is locked for 15 minutes after 5 consecutive failed logins
- [ ] ADMIN-007 event is logged on every successful admin login
- [ ] ADMIN-008/009 events logged on lockout/unlock
- [ ] Each endpoint returns HTTP 403 when accessed by a role without permission
- [ ] `GET /audit/export?format=json` returns valid NDJSON
- [ ] `POST /nas` with a 31-char secret returns HTTP 422
- [ ] VSA with mismatched vendor/attribute returns HTTP 422
- [ ] High-privilege VSA assignment by non-superadmin returns HTTP 403

### Phase 3
- [ ] Audit page displays `nas_ip_address` and `calling_station_id` columns
- [ ] `/privilege-map` page allows create, read, update, delete of user-NAS mappings
- [ ] Helpdesk user does not see NAS management or Groups menu items
- [ ] Auditor user sees only read-only audit and report pages
- [ ] NTP status indicator shows green when system clock is synchronized
- [ ] FreeRADIUS rejects authentication from a NAS not listed in `user_nas_privilege_map` for the given user (when policy is in enforce mode)

---

## Estimated Effort

| Phase | Scope | Estimate |
|-------|-------|----------|
| Phase 1 | 8 schema changes, 1 FreeRADIUS query fix | 2–3 days |
| Phase 2 | 6 new services/routers, 5 modified routers | 5–7 days |
| Phase 3 | 3 new UI pages/components, 4 modified, 1 RADIUS policy | 3–5 days |
| **Total** | | **10–15 days** |
