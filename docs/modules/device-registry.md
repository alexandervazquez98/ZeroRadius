---
goal: Document the Device Registry module so an AI agent can CRUD individual devices, run a bulk CSV import, and download/parse the CSV template.
audience: agent + human
prerequisites:
  - At least one NAS registered (the `nas_ip` column references it)
  - At least one NAS Category (optional; falls back to `default_category_id`)
inputs:
  - JWT (any role to read; admin/superadmin to write; superadmin to delete)
  - CSV file with headers: `mac, nas_ip, name, description, category_id`
outputs:
  - `device_registry` rows keyed by MAC; bulk CSV returns `{created, updated, errors[]}` counts
---

# Module — Device Registry

> **Scope:** `/device-registry/*` (router) + `frontend/src/pages/DeviceRegistry.jsx`
> + `backend/app/services/device_registry.py` (schema) +
> database table `device_registry`.

## 1. Purpose

Register endpoint devices (SMs, CPEs, modems) identified by their MAC address,
and link them to the NAS they connect to. The MAC is the natural key; bulk
imports upsert on MAC.

## 2. URL surface

Base path: `/device-registry`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `` (root) | any active user | List devices (filters: `category_id`, `nas_ip`, `is_active`) |
| `GET` | `/stats` | any active user | `{ "total": N, "active": M }` |
| `GET` | `/{device_id}` | any active user | Single device |
| `POST` | `` (root) | `admin` / `superadmin` | Create single device (409 on MAC collision) |
| `PUT` | `/{device_id}` | `admin` / `superadmin` | Update device |
| `DELETE` | `/{device_id}` | `superadmin` | Delete device |
| `POST` | `/bulk` | `admin` / `superadmin` | Bulk upsert via JSON array |
| `POST` | `/bulk/csv` | `admin` / `superadmin` | Bulk upsert via CSV upload |
| `GET` | `/bulk/template` | `admin` / `superadmin` | CSV template download |

Source: `backend/app/routers/device_registry.py`.

## 3. Schema

`DeviceRegistry` (`backend/app/models/models.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | Auto-increment |
| `mac` | str | Canonical form `XX:XX:XX:XX:XX:XX` (auto-normalised) |
| `nas_ip` | str | IP of the NAS this device connects through |
| `name` | str | Display name |
| `description` | str | Free text |
| `category_id` | int \| null | FK to `nas_categories.id` |
| `is_active` | bool | Defaults to 1 |

## 4. CSV template format

```
mac,nas_ip,name,description,category_id
0A:00:3E:45:76:4A,192.168.1.11,"SM Torre Norte","Cliente premium - sector norte",2
0A:00:3E:45:76:4B,192.168.1.12,"SM Torre Sur","Backhaul secundario",
```

- Required headers: `mac`, `nas_ip`, `name`, `description`. Missing headers → 400.
- `category_id` is optional. Empty / non-numeric → uses `default_category_id` query param (or `NULL`).
- MAC is auto-normalised; `0a:00:3E:45:76:4a` and `0A003E45764A` both produce `0A:00:3E:45:76:4A`.
- Errors are reported per-row in the response `errors[]` list (no global abort on row failure).

## 5. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# 1. Download the template
curl -sS -o /tmp/template.csv \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/device-registry/bulk/template

# 2. Edit it, then upload
curl -sS -X POST http://localhost:8000/device-registry/bulk/csv \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/tmp/template.csv" \
  -F "default_category_id=2" | jq .
```

**Expected output:**

```json
{
  "created": 2,
  "updated": 0,
  "errors": []
}
```

**Failure patterns:**

| Output | Meaning |
|---|---|
| `400 "CSV missing required header(s): mac, name, description"` | Headers missing; fix and re-upload |
| `{"errors": ["row 3: invalid mac 'XX:XX...'"]}` | Row-level MAC normalisation error; fix row, re-upload unchanged rows are not re-committed |
| `409 MAC '0A:00:3E:... already registered` | Single-device POST collision; use the bulk endpoint for upsert semantics |

## 6. Audit + rate limit

- Single device mutations: `event_code=EventCode.ADMIN_005` (`AUDIT: device registry`).
- Bulk mutations: `event_code=EventCode.ADMIN_005`, `action="BULK_CREATE"` / `"BULK_CSV"`.
- All write endpoints rate-limited (`30/minute` or `10/minute` for bulk).

## 7. Cross-references

- **NAS Categories:** [`docs/modules/nas-categories.md`](nas-categories.md)
- **CIR / Circuits:** [`docs/modules/circuits.md`](circuits.md)
- **Database:** [`docs/database.md` → device_registry](../database.md#3-zeroradius-domain-tables)
- **Architecture:** [`docs/architecture.md`](../architecture.md)
