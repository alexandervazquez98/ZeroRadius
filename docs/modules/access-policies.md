---
goal: Document the unified Access Policies module (previously "Privilege Map" + "CIR Manager") so an AI agent can resolve a RADIUS authentication to a target profile deterministically.
audience: agent + human
prerequisites:
  - Read [`docs/architecture.md`](../architecture.md) and [`docs/database.md`](../database.md)
  - Familiarity with FreeRADIUS `SQL-Group` and the project's `nas_based_authorization` policy
inputs:
  - JWT (admin or superadmin for mutations; auditor OK for reads)
  - A user already exists in `radcheck` and has at least one RADIUS group in `radgroupreply`
outputs:
  - `AccessPolicyAssignment` rows that get hydrated into `SQL-Group` at authentication time
  - Resolved CIR profile attached to the assignment
---

# Module — Access Policies

> **Scope:** `/access-policies/*` (router) + `frontend/src/pages/AccessPolicies.jsx`
> + `frontend/src/components/access-policies/*` + the database table
> `access_policy_assignments` (historically `user_nas_privilege_map`,
> renamed in migration `c0123d4`).
>
> **Why this is the unified module:** Before v1.3.0, what we now call
> "Access Policies" existed as two separate frontend concepts — *Privilege
> Map* and *CIR Manager* — backed by overlapping SQL. PR #59 unified them
> into one router + one table. The old `docs/06-cir-configuration-manual.md`
> predates the merge; the canonical reference is now **this document**. The
> original manual is retained as [`docs/06-cir-configuration-manual.md`](../06-cir-configuration-manual.md)
> with a redirect at the top.

## 1. What the module does

Access Policies decide which **RADIUS group** (and therefore which reply
attributes — including CIR values like `Cambium-Canopy-HPDLCIR`) a user
gets when authenticating against a specific **target** (NAS IP, range, segment,
or category).

Resolution happens at RADIUS protocol time via `radius/policy.d/nas_based_authorization`:

1. FreeRADIUS receives `Access-Request` with `User-Name`, `User-Password`, `NAS-IP-Address`, `Calling-Station-Id`.
2. The custom policy reads the matching `access_policy_assignments` row(s) using the precedence chain (see §4).
3. The winning row's `radius_group` is set as `control:SQL-Group`.
4. `rlm_sql` then hydrates the group reply attributes (`radgroupreply`) into the response.
5. For requests with a CIR assignment, `circuits/resolve` is also used to read the bandwidth profile.

## 2. URL surface

Base path: `/api/v1/access-policies`

| Method | Path | Roles | Notes |
|---|---|---|---|
| `GET` | `/bandwidth-profiles` | `auditor` / `admin` / `superadmin` | List all bandwidth profiles |
| `POST` | `/bandwidth-profiles` | `admin` / `superadmin` | Create a profile (201) |
| `PUT` | `/bandwidth-profiles/{profile_name}` | `admin` / `superadmin` | Update an existing profile |
| `DELETE` | `/bandwidth-profiles/{profile_name}` | `superadmin` | Delete a profile |
| `GET` | `/assignments` | `auditor` / `admin` / `superadmin` | List assignments (filters: `username`, `nas_ip`, `is_active`, `overdue_review`) |
| `POST` | `/assignments` | `admin` / `superadmin` | Create or replace an assignment (idempotent on `(username, target)`) |
| `POST` | `/assignments/bulk` | `admin` / `superadmin` | Bulk create by `nas_ips` list (no category, no segment) |
| `PUT` | `/assignments/{assignment_id}` | `admin` / `superadmin` | Update specific row |
| `DELETE` | `/assignments/{assignment_id}` | `superadmin` | Delete specific row |
| `POST` | `/preview` | `auditor` / `admin` / `superadmin` | Dry-run the resolver for `(username, nas_ip, calling_station_id)` |

Source: `backend/app/routers/access_policies.py`.

## 3. Assignment schema

`AccessPolicyAssignment` columns (most relevant subset):

| Column | Type | Purpose |
|---|---|---|
| `id` | int PK | Row id |
| `username` | str | Subject user |
| `nas_ip` | str \| null | Exact NAS IP target |
| `calling_station_id` | str \| null | Optional MAC filter |
| `nas_category_id` | int \| null | Target by NAS category |
| `segment_id` | int \| null | Target by Network Segment |
| `target_start_ip` | str \| null | Range start IP (must be inside `segment_id`) |
| `target_end_ip` | str \| null | Range end IP (must be inside `segment_id`) |
| `nas_identifier` | str \| null | Free-text NAS identifier |
| `nas_vendor` | str \| null | Vendor tag (`cisco`, `dahua`, `generic`, …) |
| `radius_group` | str | The group the user will be a member of |
| `privilege_level` | int \| null | Optional numeric privilege level |
| `justification` | str \| null | Required for audit trail (ISO 27001 A.8.2) |
| `approved_by` | str | Admin who approved |
| `review_date` | date \| null | Optional ISO 27001 A.8.2 review-date flag |
| `is_active` | bool | Logical delete flag |
| `cir_id` | int \| null | Optional CIR (Committed Information Rate) assignment |

> **Note:** The base form expects **at most one** of `nas_ip`, `nas_category_id`,
> `segment_id + (target_start_ip + target_end_ip)` per assignment. Mixed
> targets are rejected at the schema layer.

## 4. Precedence / priority / fallback chain

`radius/policy.d/nas_based_authorization` resolves the active assignment in
this deterministic order:

1. **Exact NAS-IP match** (`nas_ip == <request nas_ip>`)
2. **Range exception** within `NetworkSegment` (narrower range wins)
3. **Segment base** (`segment_id` CIDR containment; more-specific CIDR wins)
4. **NAS category fallback** (resolved through `nas_cidr_ranges` view; matches
   `nas_category_id` against the NAS's category)
5. **No match → reject** with `Reply-Message: Access denied: NAS not authorized for this user`

> See [`docs/06-cir-configuration-manual.md`](../06-cir-configuration-manual.md#4-priority--precedence-rules-enforced-at-runtime)
> for the legacy diagram that still applies.

## 5. Validation rules (enforced at the API)

- **`validate_category_membership`** (added in `4a86284`, wired in `bde396b`/`c2162a4`):
  rejects creation when the chosen `nas_category_id` is incompatible with the
  selected `nas_ip`/`calling_station_id` (e.g. mixing MAC-targeted rule with
  a category that excludes that MAC).
- **`validate_segment_exception`**:
  range exceptions (`target_start_ip`/`target_end_ip`) must lie inside the
  declared `segment_id` CIDR.
- **One active per (user, category)**: at most one active assignment per user
  per category is allowed (`PUT` returns 409 on duplicate).
- **Audit**: every CREATE / UPDATE / DELETE is logged to `app_audit_log` with
  `EventCode.ADMIN_002`, capturing old_value + new_value.

## 6. End-to-end agent run: create + resolve

```bash
# JWT
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# 1. Create an assignment: user "netops" → exact NAS IP 192.168.10.50 → group "DC-Admins"
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "netops",
    "nas_ip": "192.168.10.50",
    "radius_group": "DC-Admins",
    "privilege_level": 7,
    "justification": "NOC operator on data-center core routers",
    "approved_by": "admin",
    "is_active": true
  }' | jq .

# 2. Preview the resolution without sending RADIUS
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"netops","nas_ip":"192.168.10.50"}' | jq .

# 3. Now ask FreeRADIUS for real
docker exec radius-server bash -c '
  echo "netops Cleartext-Password := \"Test\!123\"" \
    >> /etc/raddb/mods-config/files/authorize
  radiusd -C
  radtest netops "Test\!123" 192.168.10.50 10 secret 0 127.0.0.1
'
```

**Expected output (preview):**

```json
{
  "resolution_path": "ip",
  "mapping": {
    "id": 42,
    "username": "netops",
    "nas_ip": "192.168.10.50",
    "radius_group": "DC-Admins",
    ...
  },
  "profile": null,
  "trace": [{"step": "exact_ip", "matched_assignment_id": 42, ...}]
}
```

**Expected output (FreeRADIUS):** ends with `Received Access-Accept Id <n> from 192.168.10.50:1812`.

## 7. UI surface (frontend)

Frontend: [`frontend/src/pages/AccessPolicies.jsx`](../../frontend/src/pages/AccessPolicies.jsx)
with three tabs (each a separate component under
[`frontend/src/components/access-policies/`](../../frontend/src/components/access-policies/)):

| Tab | Component | Purpose |
|---|---|---|
| Assignments | `AssignmentsTab.jsx` | CRUD on the assignment list |
| Bandwidth Profiles | `BandwidthProfilesTab.jsx` | CRUD on bandwidth profiles |
| Preview | `PreviewTab.jsx` | Live resolve against username + NAS IP |

## 8. Failure modes

| Symptom | Check | Reference |
|---|---|---|
| `409 User already has an active assignment in this category` | Look for another active row with same `username` + `nas_category_id` | §5 |
| `400 cidr must be a valid IP network CIDR` | Run from `/access-policies/preview` first to confirm exact target | [`docs/modules/network-segments.md`](network-segments.md) |
| `RADIUS rejects unexpectedly` | Check `radius_reply_audit`; run `/circuits/resolve` to confirm CIR path | [`docs/modules/circuits.md`](circuits.md) |
| `preview returns resolution_path: "none"` | No matching assignment — verify target type (ip / range / segment / category) | §4 |

## 9. Cross-references

- **Architecture / data flow:** [`docs/architecture.md` → §2.2](../architecture.md#22-nac--radius-authentication)
- **Database / `access_policy_assignments` + view `nas_cidr_ranges`:** [`docs/database.md`](../database.md#3-zeroradius-domain-tables)
- **CIR resolution:** [`docs/modules/circuits.md`](circuits.md)
- **Network Segments:** [`docs/modules/network-segments.md`](network-segments.md)
- **NAS Categories:** [`docs/modules/nas-categories.md`](nas-categories.md)
- **Live log viewer / Access-Accept events:** [`docs/04-live-log-viewer.md`](../04-live-log-viewer.md)
- **Legacy CIR manual (kept for historical reference):** [`docs/06-cir-configuration-manual.md`](../06-cir-configuration-manual.md)
