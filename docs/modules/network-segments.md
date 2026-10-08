---
goal: Document the Network Segments module so an AI agent can CRUD named CIDR ranges and reason about the overlap + dependency validation rules.
audience: agent + human
prerequisites:
  - Familiarity with CIDR notation (IPv4 + IPv6)
  - Understanding of how Access Policies use segments for range/exception targeting
inputs:
  - JWT
outputs:
  - `network_segments` rows that are guaranteed non-overlapping (within same IP family)
---

# Module — Network Segments

> **Scope:** `/network-segments/*` (router) +
> `backend/app/routers/network_segments.py` +
> database table `network_segments`.

## 1. Purpose

Define named CIDR ranges (e.g., `DC-Core = 10.1.0.0/16`) for use in Access
Policies as either **segment-base targets** (`segment_id`) or as parents of
**range exception targets** (`segment_id + target_start_ip + target_end_ip`).

## 2. URL surface

Base path: `/api/v1/network-segments`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `` | `auditor` / `admin` / `superadmin` | List segments |
| `POST` | `` | `admin` / `superadmin` | Create (201) |
| `PUT` | `/{id}` | `admin` / `superadmin` | Update (with dependency checks) |
| `DELETE` | `/{id}` | `superadmin` | Delete (fails if dependent policies) |

## 3. Schema

`NetworkSegment`:

| Column | Type | Notes |
|---|---|---|
| `id` | int PK | |
| `name` | str unique | Operator-friendly label |
| `cidr` | str | CIDR (IPv4 or IPv6) |
| `description` | str \| null | |

## 4. Validation rules

### 4.1 Overlap rejection (within IP family)

On create and on update of `cidr`, the API rejects the operation if any other
segment **of the same IP family** (`IPv4` vs `IPv6`) overlaps with the
candidate CIDR. Overlap is computed with Python's
`ipaddress.ip_network.overlaps`.

```python
# Mental model
candidate = ipaddress.ip_network("10.1.0.0/16")
existing  = ipaddress.ip_network("10.1.5.0/24")  # contained in candidate
existing.overlaps(candidate)  # True → 409
```

**Behaviour:**
- 409 if the candidate overlaps any other segment.
- Self-overlap on PUT is excluded (the row is updated, not duplicated).
- Different IP families never overlap (an IPv4 and IPv6 segment cannot
  numerically overlap).

### 4.2 Range-exception dependency check on update

When a segment's CIDR is updated, all `AccessPolicyAssignment` rows that
reference this segment with a `target_start_ip`/`target_end_ip` range are
checked. If any range would fall outside the new CIDR, the update is rejected
with 409 (and the first offending range is named in the detail message).

### 4.3 Delete dependency check

A segment cannot be deleted while any `AccessPolicyAssignment` references it:

```
409 Cannot delete network segment while dependent privilege maps exist
```

## 5. End-to-end agent run

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Create a segment
curl -sS -X POST http://localhost:8000/api/v1/network-segments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "name": "DC-Core",
    "cidr": "10.1.0.0/16",
    "description": "Data center core network (IPv4)"
  }' | jq .

# Attempt overlapping segment
curl -sS -X POST http://localhost:8000/api/v1/network-segments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"DC-Core-22","cidr":"10.1.5.0/24"}'
# → 409 {"detail": "Network segment CIDR overlaps with existing segment 'DC-Core' (10.1.0.0/16)"}
```

## 6. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| 409 "overlaps with existing segment" | Candidate CIDR touches another segment of the same family | Resize the CIDR or merge into the other segment |
| 409 "dependent exception … would fall outside the segment" | On update, an exception range in an Access Policy is now outside the new CIDR | Either keep the CIDR or remove the exception first |
| 409 "dependent privilege maps exist" | Trying to delete a segment still referenced | Delete the Access Policy first |

## 7. Cross-references

- **Access Policies (uses these as targets):** [`docs/modules/access-policies.md`](access-policies.md)
- **Database:** [`docs/database.md` → network_segments](../database.md#3-zeroradius-domain-tables)
