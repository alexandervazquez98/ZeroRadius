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
   `device_ip` is always the UDP source address of the datagram (Docker keeps
   the real source for LAN devices). The forwarder parses RFC 3164, RFC 5424,
   Cisco IOS (`45: *Nov 23 17:52:31.123: %SYS-5-CONFIG_I: ...`) and MikroTik
   (`system,info,account user ...`) bodies into `program` and `message`.
   RouterOS remote logging (default `bsd-syslog=no`) sends no `<PRI>`; then the
   severity comes from the most severe topic (`critical`=2, `error`=3,
   `warning`=4, `info`=6, `debug`=7). Lines without `<PRI>` or a severity topic
   are stored as-is with severity 6.
   Tests: `python -m pytest rsyslog/tests` (needs `requests`).
2. The backend persists each event into `syslog_events`; the integrity
   service (`syslog_integrity.py`) maintains a tamper-evident hash chain
   (`previous_hash`, `hash` columns).

## 2. URL surface

Base path: `/syslog`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `POST` | `/ingest` | `SYSLOG_API_KEY` header | Bulk insert; returns `{ "ingested": N }` |
| `GET` | `` | any active user | List with filters + DataTables-friendly partial matching |
| `GET` | `/nas-status` | any active user | Registered NAS that sent no syslog within the threshold |

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

Lists events newest first inside a time window. The window defaults to the
last 8 hours and can never be longer (`SYSLOG_QUERY_MAX_HOURS`, default 8),
so a request stays bounded however large `syslog_events` grows. There is no
total count; pages are keyset-paginated.

Query params:

| Param | Type | Notes |
|---|---|---|
| `limit` | int 1-500 | default 50 |
| `cursor` | str | `next_cursor` from the previous page; omit for the first page |
| `start_date`, `end_date` | ISO datetime (UTC) | both omitted: last 8 h; only `start_date`: the next 8 h; only `end_date`: the previous 8 h |
| `device_ip` | str | prefix match (`192.168` matches `192.168.1.50`); `%` and `_` are literal |
| `message` | str | case-insensitive substring match; `%` and `_` are literal |
| `severity` | int 0-7 | exact match |
| `facility` | int 0-23 | exact match |

```json
{
  "events": [{"id": 912, "received_at": "2026-11-25T17:52:31", "device_ip": "10.3.152.213", "...": "..."}],
  "has_more": true,
  "next_cursor": "MjAyNi0xMS0yNVQxNzo1MjozMXw5MTI",
  "start_date": "2026-11-25T10:00:00",
  "end_date": "2026-11-25T18:00:00",
  "max_range_hours": 8
}
```

**Failure modes:**

| Output | Cause |
|---|---|
| `422 "The time range cannot exceed 8 hours."` | `end_date - start_date` > 8 h |
| `422 "end_date must be after start_date."` | Reversed range |
| `422 "Invalid cursor."` | Cursor not produced by this endpoint |

### 2.3 `GET /syslog/nas-status`

Every registered NAS is expected to send syslog. A NAS is **silent** when no
event arrived from it within the threshold (`SYSLOG_SILENT_HOURS`, default 24).

| Param | Type | Notes |
|---|---|---|
| `hours` | int 1-720 | optional; overrides `SYSLOG_SILENT_HOURS` |

```json
{
  "threshold_hours": 24,
  "total": 3,
  "silent_count": 1,
  "reporting_count": 2,
  "devices": [
    {"id": 3, "nasname": "192.168.1.191", "shortname": "moxa", "last_seen": null, "silent": true}
  ]
}
```

`devices` lists every NAS, silent ones first. Matching of `nas.nasname` against
`syslog_events.device_ip`:

- IP: exact match.
- CIDR: any address inside the network counts as reporting.
- Hostname: exact string match only (syslog stores source IPs), so a
  hostname NAS shows as silent unless its events carry that exact name.

The Syslog dashboard shows this as the "NAS not sending syslog" card
(`frontend/src/components/NasSyslogStatusCard.jsx`), refreshed every 5 minutes.

## 3. Syslog integrity

`syslog_integrity.py` keeps `previous_hash` / `hash` columns on each row,
forming a SHA-256 chain (each row's `hash = sha256(previous_hash + row)`).
A break in the chain indicates tampering; tampering alerts are out of scope
for this version but the data is structured to support them.

## 3.1 Partitions and retention

`syslog_events` is RANGE-partitioned by month (`pYYYYMM` + catch-all `pmax`).
A backend job (`app/services/syslog_partitions.py`, started in `main.py`) runs
at startup and every 24 h:

1. Splits upcoming months off `pmax` (`REORGANIZE PARTITION`) so new events
   always land in their own month.
2. Drops partitions older than the retention window (`DROP PARTITION`). The
   current month plus the previous `SYSLOG_RETENTION_MONTHS` full months are
   kept, so between 3 and 4 months of logs exist at any time with the default.

| Variable | Default | Meaning |
|---|---|---|
| `SYSLOG_RETENTION_MONTHS` | `3` | Full months kept besides the current one; invalid or negative values fall back to 3 |
| `SYSLOG_PARTITIONS_AHEAD` | `3` | Months created ahead of the current one (max 24) |
| `SYSLOG_SILENT_HOURS` | `24` | Hours without syslog before a NAS is silent |

Dropping a partition deletes its events permanently. The hash chain stays
verifiable because each row is checked against its stored `previous_hash`.
If the table was created without partitions (e.g. by `create_all` instead of
`init.sql`), the job logs a warning and changes nothing.

## 3.2 Indexes

Each secondary index serves one query that would otherwise scan the table:

| Index | Serves |
|---|---|
| `idx_syslog_received_id (received_at, id)` | `GET /syslog` window + keyset order, no filesort |
| `idx_syslog_device_received (device_ip, received_at)` | `GET /syslog/nas-status` (`MAX(received_at)` per device, loose index scan) and the `device_ip` filter |
| `idx_syslog_hash_pending (hash(1))` | Hash-chain worker lookup of `hash IS NULL` rows |

Partition pruning does not apply to `received_at` ranges: the partition
expression `YEAR*100+MONTH` is not one MariaDB can prune by range, so every
query relies on these indexes instead.

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

**Expected output:** Events from the last 8 hours whose `device_ip` starts with `192.168`, at most `limit`, plus `has_more` / `next_cursor`.

## 5. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Backend logs `401 "Invalid API key"` after ingestion | `SYSLOG_API_KEY` rotated in `.env` but `radius-syslog` container not recreated | `docker compose up -d syslog` |
| Events ingested but not visible in `/syslog` UI | Operator lacks `admin`+ role | Use a higher-role token |
| Hash chain mismatch | Tampering or partial-write recovery | Run the integrity checker (planned) |
| Log: `syslog_events is not partitioned; skipping partition maintenance` | Table created without `PARTITION BY` | Recreate it from `database/init.sql` |
| Registered NAS always silent | `nasname` is a hostname, or the device sends syslog from another IP (another interface, or NAT in between) | Check `device_ip` of its events and register the NAS by that IP or a CIDR |

## 6. Cross-references

- **Deployment / port 514:** [`docs/deployment.md`](../deployment.md)
- **Live log viewer (WebSocket on Docker stdout, complement):** [`docs/04-live-log-viewer.md`](../04-live-log-viewer.md)
- **Audit export (SIEM):** [`docs/modules/audit.md`](audit.md)
