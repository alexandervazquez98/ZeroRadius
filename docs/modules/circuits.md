---
goal: Document the Circuits (CIR) module so an AI agent can CRUD circuits, link them to Access Policies, and resolve the winning CIR for a given (user, NAS) tuple.
audience: agent + human
prerequisites:
  - Read [`docs/modules/access-policies.md`](access-policies.md) (the module that uses Circuits)
  - Familiarity with FreeRADIUS CIR reply attributes (`Cambium-Canopy-HPDLCIR`, etc.)
inputs:
  - JWT
outputs:
  - `circuits` rows linked to `access_policy_assignments.cir_id`
  - `circuits/resolve` preview returning the winning circuit + the resolution trace
---

# Module — Circuits

> **Scope:** `/circuits/*` (router) + `frontend/src/pages/CircuitPage.jsx`
> + `backend/app/services/circuit_service.py` +
> `backend/app/services/bandwidth_profiles.py` +
> database table `circuits`.

## 1. Purpose

A **Circuit** is a named mapping between a NAS IP, a `circuit_id`, and CIR
information (downstream/upstream rates). It is referenced from
`AccessPolicyAssignment.cir_id`, which in turn drives the FreeRADIUS reply
attributes (`Cambium-Canopy-HPDLCIR := …`) at authentication time.

The companion model is **BandwidthProfile** (managed under `/access-policies/bandwidth-profiles`), which carries the human-friendly CIR parameters.

## 2. URL surface

Base path: `/circuits`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `` | `auditor` / `admin` / `superadmin` | List circuits |
| `GET` | `/resolve` | `auditor` / `admin` / `superadmin` | Resolve CIR for `(username, nas_ip, calling_station_id?)` |
| `GET` | `/{circuit_id}` | `auditor` / `admin` / `superadmin` | Single circuit |
| `POST` | `` | `admin` / `superadmin` | Create circuit |
| `PUT` | `/{circuit_id}` | `admin` / `superadmin` | Update circuit |
| `DELETE` | `/{circuit_id}` | `superadmin` | Delete (fails if dependent policies) |

## 3. Resolution endpoint

```text
GET /circuits/resolve?username=<u>&nas_ip=<n>&calling_station_id=<m>
```

Returns:

```ts
{
  resolution_path: "cir" | "none",
  mapping: AccessPolicyAssignmentOut | null,   // the winning assignment
  profile: BandwidthProfileOut | null,         // the bandwidth profile if mapping.radius_group starts with "cir_"
  trace: [                                     // human-readable trace
    { step: "exact_ip", matched_assignment_id: ..., },
    ...
  ]
}
```

> **Path-ordering note:** `/resolve` is declared **before** `/{circuit_id}` so a
> literal segment like `"resolve"` does not get caught by the int path-param
> matcher. (See commit `77fcc8c`.)

## 4. Schema

`Circuit`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | str unique | Operator-friendly label |
| `circuit_id` | int unique | FreeRADIUS `circuit_id` |
| `nas_ip` | str | IP of the NAS the circuit attaches to |
| `bandwidth_down` | int | Downstream CIR (kbps) |
| `bandwidth_up` | int | Upstream CIR (kbps) |
| `description` | str \| null | |

`BandwidthProfile` (lives under `/access-policies/bandwidth-profiles`):

| Column | Notes |
|---|---|
| `name` | PK; pattern `cir_*` recommended |
| `downstream_kbps` | int |
| `upstream_kbps` | int |
| `burst_allowance_kbps` | int \| null |
| `description` | str \| null |

## 5. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# 1. Create a bandwidth profile (group + CIR values)
curl -sS -X POST http://localhost:8000/access-policies/bandwidth-profiles \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "cir_premium_50m",
    "downstream_kbps": 51200,
    "upstream_kbps": 25600,
    "burst_allowance_kbps": 8192,
    "description": "Premium 50M / 25M"
  }' | jq .

# 2. Create a circuit pointing to NAS 192.168.10.50
curl -sS -X POST http://localhost:8000/circuits \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "circ-torre-norte",
    "circuit_id": 1001,
    "nas_ip": "192.168.10.50",
    "bandwidth_down": 51200,
    "bandwidth_up": 25600
  }' | jq .

# 3. Resolve the CIR for a test user against that NAS
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/circuits/resolve?username=netops&nas_ip=192.168.10.50" | jq .
```

**Expected output (last command):**

```json
{
  "resolution_path": "cir",
  "mapping": { "id": 99, "username": "netops", "radius_group": "DC-Admins", "cir_id": 1001 },
  "profile": {
    "name": "cir_premium_50m",
    "downstream_kbps": 51200,
    "upstream_kbps": 25600
  },
  "trace": [...]
}
```

## 6. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| 400 "Circuit name already exists" | Duplicate `name` | Use a unique name |
| 400 "Circuit ID already exists" | Duplicate `circuit_id` | Pick a distinct id |
| 409 "Cannot delete circuit while dependent access policy assignments exist" | At least one AccessPolicyAssignment references the circuit | Detach first (`PUT /access-policies/assignments/{id}` with `cir_id=null`) |
| `resolve` returns `resolution_path: "none"` | No Access Policy mapping this (user, NAS) tuple | Create one first |
| `null` MAC normalisation error from `/resolve?calling_station_id=...` | `calling_station_id` not parseable as MAC | Drop the param or supply a valid MAC |

## 7. Cross-references

- **Access Policies (`cir_id`):** [`docs/modules/access-policies.md`](access-policies.md)
- **Bandwidth Profiles (parallel resource under access-policies):** [`docs/modules/access-policies.md`](access-policies.md#2-url-surface)
- **Database:** [`docs/database.md` → circuits](../database.md#3-zeroradius-domain-tables)
- **Legacy CIR manual:** [`docs/06-cir-configuration-manual.md`](../06-cir-configuration-manual.md)
