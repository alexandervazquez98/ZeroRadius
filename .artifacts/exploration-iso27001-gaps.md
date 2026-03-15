# Gap Analysis: ISO 27001 Compliance — RADIUS-gestor

**Date**: 2026-03-14
**Session**: sdd-improve-radius-gestor-2026-03-14
**Project**: RADIUS-gestor

---

## What Already Works (Compliant)

| Feature | Location | Control |
|---------|----------|---------|
| Basic CRUD admin audit (ADMIN-001 to 005) | `backend/app/services/audit.py` | A.8.15 |
| bcrypt password hashing for admin users | `backend/app/core/security.py` | A.5.17 |
| Forced password change on first login | `backend/app/routers/auth.py` | A.5.17 |
| NAS CRUD with audit trail | `backend/app/routers/nas.py` | A.8.15 |

---

## Critical Gaps (CRÍTICA Priority)

### GAP-C1: PAP Passwords Stored in Plain Text
- **File**: `radius/sql:54`
- **Control**: A.5.17 (Management of secret authentication information)
- **Issue**: `radpostauth` logs include the raw PAP password in the `reply` column. Any SQL-level access exposes credentials.
- **Fix**: Remove password from FreeRADIUS SQL logging query.

### GAP-C2: radpostauth Missing Forensic NAS Fields
- **File**: `database/init.sql:101`
- **Control**: A.8.15 (Logging)
- **Issue**: `radpostauth` lacks: `nas_ip_address`, `calling_station_id`, `nas_identifier`, `reply_message`, `event_source`, `integrity_hash`. Incomplete for forensic audit trail.
- **Fix**: ALTER TABLE to add missing columns; update FreeRADIUS SQL queries.

### GAP-C3: authdate Mutable via ON UPDATE
- **File**: `database/init.sql:106`
- **Control**: A.5.33 (Protection of audit logs)
- **Issue**: `authdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` — any row update silently modifies the timestamp, destroying temporal integrity.
- **Fix**: Remove `ON UPDATE CURRENT_TIMESTAMP` from `authdate` column.

### GAP-C4: No Account Lockout After Failed Attempts
- **File**: `backend/app/routers/auth.py`
- **Control**: A.8.16 (Monitoring activities)
- **Issue**: No mechanism to detect or block brute-force login attempts against admin console.
- **Fix**: Add `login_attempts` table + lockout logic (e.g., 5 failures → 15-minute lockout).

### GAP-C5: No SHA-256 Integrity Hashes on Audit Records
- **File**: `backend/app/services/audit.py`
- **Control**: A.5.33 (Protection of audit logs)
- **Issue**: Audit records can be tampered silently; no hash chain exists.
- **Fix**: Compute `SHA-256(event_code + actor + target + timestamp + prev_hash)` and store in `integrity_hash` column.

### GAP-C6: Tables radius_reply_audit and user_nas_privilege_map Missing
- **File**: `database/init.sql`
- **Controls**: A.5.18 (Access rights), A.8.2 (Privileged access rights)
- **Issue**: No per-user NAS privilege mapping exists; no separate reply attribute audit table.
- **Fix**: Create both tables in migration.

---

## High-Priority Gaps (ALTA)

### GAP-H7: No Role System
- **Files**: `backend/app/core/security.py`, `AdminUser` model
- **Control**: SOD-01..06 (Segregation of duties)
- **Issue**: All admin users have full access; no superadmin/admin/helpdesk/auditor distinction.
- **Fix**: Add `role` column to `admin_users`; add RBAC decorators to all endpoints.

### GAP-H8: No NAS-Conditional Authorization in FreeRADIUS
- **Files**: `radius/` (unlang policy files)
- **Control**: A.8.3 (Information access restriction)
- **Issue**: FreeRADIUS grants access regardless of NAS identity; no per-NAS policy enforcement.
- **Fix**: Add unlang policy to check `NAS-IP-Address` + `user_nas_privilege_map` via SQL.

### GAP-H9: No SIEM JSON Export Endpoint
- **File**: `backend/app/routers/audit.py`
- **Control**: A.8.16 (Monitoring activities)
- **Issue**: No machine-readable export of audit logs for SIEM integration.
- **Fix**: Add `GET /audit/export?format=json&from=&to=` endpoint returning NDJSON/JSON array.

### GAP-H10: No NAS Secret Minimum Length Validation
- **File**: `backend/app/routers/nas.py`
- **Control**: A.5.17 (Management of secret authentication information)
- **Issue**: NAS shared secrets can be any length; ISO 27001 recommends ≥ 32 chars.
- **Fix**: Add Pydantic validator enforcing minimum 32-character NAS secrets.

### GAP-H11: No Structured Event Codes
- **File**: `backend/app/services/audit.py`
- **Control**: A.8.15 (Logging)
- **Issue**: Audit events lack standardized codes (AUTH-001..007, ACCT-001..004, ADMIN-001..009).
- **Fix**: Define event code enum; update all audit calls to use codes.

### GAP-H12: No VSA Consistency Validation
- **File**: `backend/app/routers/groups.py`
- **Control**: REQ-VSA-02
- **Issue**: Vendor-Specific Attributes can be saved with mismatched vendor/attribute combinations.
- **Fix**: Add validation layer mapping NAS vendor to allowed VSA attribute IDs.

### GAP-H13: No High-Privilege VSA Guard
- **File**: `backend/app/routers/groups.py`
- **Controls**: A.8.2, REQ-VSA-03
- **Issue**: Any admin can assign high-privilege VSAs (e.g., Cisco-Priv-Lvl=15) without elevated permission check.
- **Fix**: Require `superadmin` role for VSAs flagged as high-privilege.

### GAP-H14: No NTP Sync Monitoring
- **Files**: None (missing feature)
- **Control**: A.8.17 (Clock synchronization)
- **Issue**: No mechanism to verify system clock is NTP-synchronized; stale timestamps in audit logs go undetected.
- **Fix**: Add backend endpoint that checks NTP offset; expose status in UI.

### GAP-H15: Audit UI Missing NAS IP and Calling Station Columns
- **File**: `frontend/src/pages/Audit.jsx`
- **Control**: A.8.15 (Logging)
- **Issue**: Audit table does not display `nas_ip_address` or `calling_station_id`.
- **Fix**: Add columns to Audit page table once GAP-C2 is resolved.

### GAP-H16: No Privilege Mapping Page
- **File**: frontend (missing page)
- **Control**: A.5.18 (Access rights)
- **Issue**: No UI to manage `user_nas_privilege_map` table.
- **Fix**: Create new React page with CRUD for user-NAS privilege assignments.

### GAP-H17: No Role-Based UI Visibility
- **Files**: frontend components/navigation
- **Control**: SOD-01..06
- **Issue**: All menu items visible to all roles; auditor-only users can see admin operations.
- **Fix**: Implement role-aware navigation and component guards.

### GAP-H18: radacct Missing Compliance Fields
- **File**: `database/init.sql:63`
- **Control**: A.8.15 (Logging)
- **Issue**: `radacct` lacks `nasidentifier`, `privilege_level`, `vendor_reply_attrs` columns needed for full accounting audit trail.
- **Fix**: ALTER TABLE radacct to add missing columns.

---

## Summary

| Priority | Count | Gaps |
|----------|-------|------|
| CRÍTICA | 6 | C1–C6 |
| ALTA | 12 | H7–H18 |
| **Total** | **18** | |
