---
goal: Provide a complete, navigable index of every REST endpoint exposed by `/api/v1`, so an AI agent can locate the right route without re-reading the source.
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
> - All routes live under `/api/v1/` unless noted otherwise.
> - All writes are rate-limited (see [`docs/modules/rate-limiting.md`](modules/rate-limiting.md)).
> - All mutations emit an entry in `app_audit_log` with the module's
>   `EventCode.ADMIN_*` constant.

## 0. Authentication

| Method | Path | Roles | Notes |
|---|---|---|---|
| `POST` | `/auth/token` | none | Form-encoded (`username`, `password`) → JWT |
| `POST` | `/auth/change-password` | active user | Body: `{"current_password", "new_password"}` |
| `GET` | `/users` | active | List /admin users (read-only route mapping) |
| `GET` | `/system/version` | none | Returns `{"version": "x.y.z"}` |
| `GET` | `/system/health` | none | `{"status": "ok"}` |
| `GET` | `/health/containers` | `admin` / `superadmin` | Per-container resource snapshot |
| `GET` | `/health/resources` | `admin` / `superadmin` | Host resource snapshot |
| `WS` | `/system/logs/stream` | `admin` / `superadmin` | WebSocket: live FreeRADIUS stdout |
| `POST` | `/sessions/*` | active | Active session management |

> `POST /auth/token` is not rate-limited through the limiter (so lockout
> still applies). See [`docs/modules/admin-users.md`](modules/admin-users.md#4-forced-password-change).

## 1. Core CRUD by domain

For each domain, deep documentation lives under `docs/modules/<name>.md`.

| Domain | Module doc | Router paths |
|---|---|---|
| NAS / RADIUS clients | (no doc — see `routers/nas.py`) | `/nas` (CRUD) ; `/nas-categories` (CRUD) — see [`docs/modules/nas-categories.md`](modules/nas-categories.md) |
| Groups (RADIUS groups) | (no doc — see `routers/groups.py`) | `/groups` ; `/groups/{id}` |
| Sessions | (no doc — see `routers/sessions.py`) | `/sessions` |
| Audit | [`docs/modules/audit.md`](modules/audit.md) | `/audit/admin`, `/audit/access`, `/audit/export` |
| Dictionaries | [`docs/modules/dictionaries.md`](modules/dictionaries.md) | `/dictionary/files`, `/upload`, `/rename`, `/content/{fn}`, `/builtin`, `/attributes`, `/values/{attr}`, `/radius-logs` |
| Admin users | [`docs/modules/admin-users.md`](modules/admin-users.md) | `/admin-users`, `/admin-users/{id}`, `/admin-users/{id}/unlock` |
| Syslog | [`docs/modules/syslog-dashboard.md`](modules/syslog-dashboard.md) | `/syslog/ingest`, `/syslog` |
| Network Segments | [`docs/modules/network-segments.md`](modules/network-segments.md) | `/network-segments`, `/network-segments/{id}` |
| Access Policies | [`docs/modules/access-policies.md`](modules/access-policies.md) | `/access-policies/assignments` (CRUD + bulk + preview); `/access-policies/bandwidth-profiles` |
| Circuits (CIR) | [`docs/modules/circuits.md`](modules/circuits.md) | `/circuits`, `/circuits/resolve`, `/circuits/{id}` |
| Device Registry | [`docs/modules/device-registry.md`](modules/device-registry.md) | `/device-registry`, `/device-registry/{id}`, `/device-registry/bulk`, `/device-registry/bulk/csv`, `/device-registry/bulk/template`, `/device-registry/stats` |

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
