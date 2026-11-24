---
goal: Provide a complete, navigable index of every REST endpoint exposed at the FastAPI root (no `/api/v1` prefix — the backend mounts routes directly under `/`), so an AI agent can locate the right route without re-reading the source.
audience: agent
prerequisites:
  - Stack running and JWT obtainable (see [`docs/00-agent-quickstart.md`](00-agent-quickstart.md))
  - Understanding of role hierarchy (`superadmin > admin > auditor`)
inputs:
  - JWT (required for everything except `/auth/token`)
outputs:
  - HTTP response per the route's documented schema
---

# API Reference

> **Conventions:**
> - All routes live under `/` unless noted otherwise.
> - All writes are rate-limited (see [`docs/modules/rate-limiting.md`](modules/rate-limiting.md)).
> - All mutations emit an entry in `app_audit_log` with the module's
>   `EventCode.ADMIN_*` constant.

## 0. Authentication

| Method | Path | Roles | Notes |
|---|---|---|---|
| `POST` | `/auth/token` | none | Form-encoded (`username`, `password`) → JWT |
| `POST` | `/auth/change-password` | active user | Body: `{"current_password", "new_password"}` |
| `GET` | `/users` | active | List RADIUS user check attributes (`radcheck`). Password values are never returned: password rows have `value: null` and `has_password: true` |
| `POST` | `/users/check` | `admin` / `superadmin` / `helpdesk` | Create a RADIUS user attribute row. `readonly` and `auditor` get 403 |
| `POST` | `/users/reply` | `admin` / `superadmin` / `helpdesk` | Add a reply attribute (privileges, e.g. `Motorola-Cambium-Canopy-UserLevel`). `readonly` and `auditor` get 403 |
| `DELETE` | `/users/reply/{id}` | `admin` / `superadmin` / `helpdesk` | Remove a reply attribute. `readonly` and `auditor` get 403 |
| `PUT` | `/users/check/{id}` | `admin` / `superadmin` | Omit `value` to keep the current password; changing a password attribute requires a new `value` (422 otherwise); a password `value` is accepted only for `Cleartext-Password` / `MD5-Password` / `NT-Password` (422 for `Crypt-Password`, `SSHA-Password`, …). The UI changes passwords only through reset-password |
| `POST` | `/users/check/{id}/reset-password` | `admin` / `superadmin` | Body: `{"password": "..."}` or `{"generate": true}`, optional `password_type` (`Cleartext-Password` / `MD5-Password` / `NT-Password`, default: current). Returns `generated_password` only when generated (shown once). Audited as `PASSWORD_RESET` without the value. Revokes a pending setup link |
| `POST` | `/users/check/{id}/setup-link` | `admin` / `superadmin` | Body: optional `password_type` (default: current). Returns a one-time `token` (shown once; the UI builds `<origin>/setup-password/<token>`) valid 72 h. **Blocks the current password immediately**; revokes a previous pending link. `GET /users` shows `setup_link.status` (`pending` / `expired` / `used` / `revoked`), `created_by`, `expires_at`. Audited as `PASSWORD_SETUP_LINK_CREATED` |
| `GET` | `/password-setup/{token}` | none (token) | `{"username", "expires_at"}` while valid; 404 unknown token, 410 used / expired / replaced |
| `POST` | `/password-setup/{token}` | none (token) | Body: `{"password"}`. Sets the password with the type chosen by the admin and consumes the link (single use, atomic). Audited as `PASSWORD_SETUP_LINK_USED` |
| `GET` | `/` | none | Welcome message |
| `GET` | `/health` | none | `{"status": "ok", "services": {...}}` (database and dependency checks); used by the container healthcheck |
| `GET` | `/system/ntp-status` | `admin` / `superadmin` | Clock offset measured with one SNTP request to `NTP_SERVER`: `synchronized`, `offset_ms`, `stratum`, `reference_server`, `last_sync`, `alert` (offset > 500 ms or no valid reply), `configured` (`false` when `NTP_SERVER` is unset; then `alert` is `false`). Cached 60 s |
| `GET` | `/system/health/containers` | `admin` / `superadmin` | Resource snapshot of the containers of this compose project only (label `com.docker.compose.project`; `COMPOSE_PROJECT_NAME` overrides detection; empty list if unknown). Cached 10 s |
| `GET` | `/system/health/resources` | `admin` / `superadmin` | Host resource snapshot |
| `WS` | `/system/logs/stream` | `admin` / `superadmin` | WebSocket: live FreeRADIUS stdout |
| `POST` | `/sessions/*` | active | Active session management |

> `POST /auth/token` is not rate-limited through the limiter (so lockout
> still applies). See [`docs/modules/admin-users.md`](modules/admin-users.md#4-forced-password-change).

## 1. Core CRUD by domain

For each domain, deep documentation lives under `docs/modules/<name>.md`.

| Domain | Module doc | Router paths |
|---|---|---|
| NAS / RADIUS clients | [`docs/01-nas-provisioning.md`](01-nas-provisioning.md) | `/nas` (CRUD), `/nas/bulk/csv`, `/nas/bulk/template` ; `/nas-categories` (CRUD) — see [`docs/modules/nas-categories.md`](modules/nas-categories.md) |
| Groups (RADIUS groups) | (no doc — see `routers/groups.py`) | `/groups` ; `/groups/{id}` |
| Sessions | (no doc — see `routers/sessions.py`) | `/sessions` |
| Audit | [`docs/modules/audit.md`](modules/audit.md) | `/audit/admin`, `/audit/access`, `/audit/export` |
| Dictionaries | [`docs/modules/dictionaries.md`](modules/dictionaries.md) | `/dictionary/files`, `/upload`, `/rename`, `/content/{fn}`, `/builtin`, `/attributes`, `/values/{attr}`, `/radius-logs` |
| Admin users | [`docs/modules/admin-users.md`](modules/admin-users.md) | `/admin-users`, `/admin-users/{id}`, `/admin-users/{id}/unlock` |
| RADIUS user passwords | [`docs/modules/radius-users.md`](modules/radius-users.md) | `/users/check/{id}/reset-password`, `/users/check/{id}/setup-link`, `/password-setup/{token}` |
| Syslog | [`docs/modules/syslog-dashboard.md`](modules/syslog-dashboard.md) | `/syslog/ingest`, `/syslog`, `/syslog/nas-status` |
| Network Segments | [`docs/modules/network-segments.md`](modules/network-segments.md) | `/network-segments`, `/network-segments/{id}` |
| Access Policies | [`docs/modules/access-policies.md`](modules/access-policies.md) | `/access-policies/assignments` (CRUD + bulk + preview); `/access-policies/bandwidth-profiles` |
| Circuits (CIR) | [`docs/modules/circuits.md`](modules/circuits.md) | `/circuits`, `/circuits/resolve`, `/circuits/{id}` |
| Device Registry | [`docs/modules/device-registry.md`](modules/device-registry.md) | `/device-registry`, `/device-registry/{id}`, `/device-registry/bulk`, `/device-registry/bulk/csv`, `/device-registry/bulk/template`, `/device-registry/stats` |

### NAS bulk import

| Method | Path | Roles | Notes |
|---|---|---|---|
| `POST` | `/nas/bulk/csv` | `admin` / `superadmin` | Multipart field `file` (UTF-8 CSV, BOM allowed, ≤ 1 MB → 413, ≤ 5000 data rows → 422). Columns `nasname, shortname, secret, category, type, description`, separated by `,` or `;` (decided by the header line); `nasname` and `secret` headers are required (422 otherwise). Query: `default_category_id` (used when a row's `category` is empty; 422 if unknown), `dry_run=true` (validate only, write nothing). Rows are validated like `POST /nas`, plus `secret` ≤ 60 chars and `category` must be an existing category name. A nasname matching one existing row updates it; matching several rows or repeating inside the file is a row error. Returns `{"created", "updated", "errors": [{"row", "nasname", "error"}], "dry_run"}` (`row` is the 1-based data row). Valid rows are committed together with one `BULK_CSV` audit entry (counts only, no secrets). Does not restart FreeRADIUS. Rate limit 10/minute |
| `GET` | `/nas/bulk/template` | `admin` / `superadmin` | CSV template with the header and two sample rows (documentation addresses, placeholder secrets) |

## 2. Endpoint shapes (request / response)

For request bodies and response schemas, consult the matching module doc.
All Pydantic schemas are in `backend/app/schemas/`.

## 3. Pagination conventions

- `limit`: defaults to 50, hard cap 100 on audit endpoints; cap 500 on
  `/syslog`.
- `offset`: zero-based; combine with `limit` to iterate.
- `response.model=list[T]`: a plain array (no envelope). `GET /syslog` is
  the exception — it returns `{ events: [...], total: N }`.
- `GET /audit/export`: when JSON and ≥ 1000 results, the response is a
  streaming `Transfer-Encoding: chunked` JSON array.

## 4. Standard error shapes

| Status | Body | Cause |
|---|---|---|
| 400 | `{"detail": "..."}` | Pydantic validation, duplicate name, missing header |
| 401 | `{"detail": "Not authenticated"}` | Missing / invalid JWT |
| 403 | `{"detail": "..."}` | Role gate blocked the request; `force_password_change` pending |
| 404 | `{"detail": "..."}` | Entity not found |
| 409 | `{"detail": "..."}` | Conflict (duplicate MAC, category overlap, dependency blocks) |
| 422 | `{"detail": "..."}` | Schema validation failed; explicit value checks |
| 429 | `{"detail": "Rate limit exceeded: ..."}` | Slowapi limit hit |
| 500 | `{"detail": "..."}` | Unhandled server error |
| 503 | `{"detail": "..."}` | Downstream dependency unavailable (e.g. `radius-server` not running for built-in dictionary queries) |

## 5. Cross-references

- **Modules:** [`docs/modules/`](modules/)
- **Architecture:** [`docs/architecture.md`](architecture.md)
- **Deployment / ports:** [`docs/deployment.md`](deployment.md)
- **Testing:** [`docs/testing.md`](testing.md)
- **Security:** [`docs/security-coverage.md`](security-coverage.md)
