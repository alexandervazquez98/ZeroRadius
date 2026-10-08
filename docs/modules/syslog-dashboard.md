---
goal: Document the Syslog module so an AI agent can ingest network device syslog and query the resulting events.
audience: agent + human
prerequisites:
  - Running `radius-syslog` container with `SYSLOG_API_KEY` matching backend
  - Network devices sending syslog to UDP 514
inputs:
  - Syslog UDP packets from devices (forwarded by `radius-syslog`)
  - JWT for reads
outputs:
  - `syslog_events` rows; ingestion acknowledged with `{ "ingested": N }`
---

# Module — Syslog

> **Scope:** `/syslog/*` (router) + `frontend/src/pages/SyslogDashboard.jsx`
> + the `radius-syslog` sidecar container +
> `backend/app/services/syslog_integrity.py` +
> database table `syslog_events`.

## 1. Purpose

A two-tier pipeline:

1. The **radius-syslog** sidecar container listens on UDP 514 for RFC-3164
   syslog from network devices (routers, switches, APs). It batches up to 50
   messages or 5 s, then `POST`s them to `/syslog/ingest`.
2. The backend persists each event into `syslog_events`; the integrity
   service (`syslog_integrity.py`) maintains a tamper-evident hash chain
   (`previous_hash`, `hash` columns).

## 2. URL surface

Base path: `/syslog`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `POST` | `/ingest` | `SYSLOG_API_KEY` header | Bulk insert; returns `{ "ingested": N }` |
| `GET` | `` | any active user | List with filters + DataTables-friendly partial matching |

### 2.1 `POST /ingest`

```bash
curl -sS -X POST http://radius-backend:8000/syslog/ingest \
  -H "X-API-Key: $SYSLOG_API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {"received_at": "2026-04-25T20:30:00Z",
     "device_ip": "192.168.10.50",
     "facility": 16, "severity": 6,
     "program": "sshd",
     "message": "Accepted publickey for ops from 10.0.0.5 port 51234 ssh2"}
  ]'
```

**Failure modes:**

| Output | Cause |
|---|---|
| `401 "Invalid API key"` | `SYSLOG_API_KEY` does not match |
| `400 "No events provided"` | Empty payload |
| 5xx | DB error |

### 2.2 `GET /syslog`

Query params:

| Param | Type | Notes |
|---|---|---|
| `limit` | int 1-500 | default 50 |
| `offset` | int ≥ 0 | pagination |
| `start_date`, `end_date` | ISO datetime | range filter |
| `device_ip` | str | case-insensitive partial match (`192.168` matches `192.168.1.50`) |
| `message` | str | case-insensitive substring match |
| `severity` | int 0-7 | exact match |
| `facility` | int 0-23 | exact match |

## 3. Syslog integrity

`syslog_integrity.py` keeps `previous_hash` / `hash` columns on each row,
forming a SHA-256 chain (each row's `hash = sha256(previous_hash + row)`).
A break in the chain indicates tampering; tampering alerts are out of scope
for this version but the data is structured to support them.

## 4. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Send a fake syslog event for "192.168.10.50"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
curl -sS -X POST http://localhost:8000/syslog/ingest \
  -H "X-API-Key: syslog-secret-key" \
  -H "Content-Type: application/json" \
  -d "[{\"received_at\":\"$NOW\",\"device_ip\":\"192.168.10.50\",\"facility\":16,\"severity\":6,\"program\":\"sshd\",\"message\":\"agent-smoke-test login from 10.0.0.5\"}]"

# Verify it was ingested
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/syslog?device_ip=192.168&limit=10" | jq .
```

**Expected output:** A list with at least one matching entry, total count near `limit`.

## 5. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Backend logs `401 "Invalid API key"` after ingestion | `SYSLOG_API_KEY` rotated in `.env` but `radius-syslog` container not recreated | `docker compose up -d syslog` |
| Events ingested but not visible in `/syslog` UI | Operator lacks `admin`+ role | Use a higher-role token |
| Hash chain mismatch | Tampering or partial-write recovery | Run the integrity checker (planned) |

## 6. Cross-references

- **Deployment / port 514:** [`docs/deployment.md`](../deployment.md)
- **Live log viewer (WebSocket on Docker stdout, complement):** [`docs/04-live-log-viewer.md`](../04-live-log-viewer.md)
- **Audit export (SIEM):** [`docs/modules/audit.md`](audit.md)
