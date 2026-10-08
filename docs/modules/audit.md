---
goal: Document the Audit module so an AI agent can query administrative actions and FreeRADIUS auth outcomes, and stream SIEM-style exports.
audience: agent + human
prerequisites:
  - Running stack with audit-capable users (auditor / admin / superadmin)
inputs:
  - JWT (auditor / admin / superadmin)
outputs:
  - `app_audit_log` rows; `radpostauth` rows; SIEM export stream
---

# Module — Audit

> **Scope:** `/audit/*` (router) + `frontend/src/pages/Audit.jsx` (single page, tabs)
> + `backend/app/services/audit.py` + database tables `app_audit_log` and
> `radpostauth`.

## 1. Purpose

Two streams of evidence surface here:

- **Admin actions**: every CRUD write goes through `app_audit_log` with
  `EventCode.ADMIN_*` (e.g., `ADMIN_001 CREATE admin_users`,
  `ADMIN_005 BULK device_registry`).
- **FreeRADIUS auth outcomes**: every `Access-Accept` / `Access-Reject` is
  written to `radpostauth` by `rlm_sql` and exposed under `/audit/access`.

## 2. URL surface

Base path: `/api/v1/audit`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `/admin` | `auditor` / `admin` / `superadmin` | List `app_audit_log` rows (search + pagination) |
| `GET` | `/access` | any active user | List `radpostauth` rows (search + NAS filter) |
| `GET` | `/export` | `auditor` / `admin` / `superadmin` | SIEM export, JSON or CSV |

### 2.1 `GET /audit/admin`

| Param | Default | Notes |
|---|---|---|
| `skip` | 0 | offset |
| `limit` | 50 (max 100) | page size |
| `search` | None | Partial match across `admin_user`, `action`, `table_affected`, `target_user` |

### 2.2 `GET /audit/access`

| Param | Default | Notes |
|---|---|---|
| `skip` | 0 | offset |
| `limit` | 50 (max 100) | page size |
| `search` | None | Partial match across `username`, `reply` |
| `nas_ip` | None | Exact match |

### 2.3 `GET /audit/export`

| Param | Default | Allowed |
|---|---|---|
| `format` | `json` | `json` \| `csv` |
| `from`, `to` | None | ISO 8601 datetime |
| `event_type` | None | `AUTH` \| `ACCT` \| `ADMIN` (prefix match on `action`) |

If `format=json` and result size ≥ 1000, the response is a streamed array
(uses `StreamingResponse`).

Every export **records an audit event itself** with `EventCode.ADMIN_008`
(`SIEM export`); operators are advised to know exports are tracked.

## 3. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Pull recent admin actions
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/audit/admin?limit=20" | jq '.[] | {id,admin_user,action,table_affected,target_user}'

# Pull last 20 access decisions for NAS 192.168.10.50
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/audit/access?nas_ip=192.168.10.50&limit=20" | jq '.'

# Export to CSV for the last day
FROM=$(date -u -d '1 day ago' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v-1d +"%Y-%m-%dT%H:%M:%SZ")
curl -sS -H "Authorization: Bearer $TOKEN" \
  -o audit-export.csv \
  "http://localhost:8000/api/v1/audit/export?format=csv&from=$FROM"
```

**Expected output (last command):** A `Content-Type: text/csv` file with header
`event_id,timestamp_utc,admin_user,target_user,action,table_affected` and one
row per audit record (≥ 1, since the export call itself is audited).

## 4. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| 422 "Invalid 'from' date format" | Non-ISO 8601 `from` / `to` | Use `YYYY-MM-DDTHH:MM:SSZ` or RFC 3339 |
| Export stream truncates | Client not handling `Transfer-Encoding: chunked` | Use `curl --no-buffer -o` |
| Empty result despite recent activity | Wrong `from` window | Drop the `from` param to default |

## 5. Cross-references

- **Event codes:** declared in `backend/app/services/audit.py`.
- **Access post-auth trail (radpostauth):** [`docs/architecture.md`](../architecture.md)
- **Security threats covered:** [`docs/security-coverage.md` → A09](../security-coverage.md#a09-security-logging-and-monitoring-failures)
- **Live log viewer (WebSocket on FreeRADIUS stdout, complements this):** [`docs/04-live-log-viewer.md`](../04-live-log-viewer.md)
