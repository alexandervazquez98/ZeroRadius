---
goal: Validate that when multiple Access Policy targeting modes overlap (exact IP, segment base, exception range, category), the precedence chain resolves deterministically.
audience: agent + human
prerequisites:
  - Healthy stack
  - Network Segments module available
  - JWT (admin/superadmin)
inputs:
  - Two `NetworkSegment` rows: parent (`10.1.0.0/16`) and child (`10.1.5.0/24`) — but cidrs must NOT overlap; use disjoint ranges for the demo (`10.1.0.0/16` and `10.2.0.0/16`)
  - One category
  - Four Access Policy assignments covering all four precedence levels
outputs:
  - For each hit, `/access-policies/preview` returns the expected `resolution_path`
backout: deletes segments + assignments; preserves category
---

# Simulation 04 — Network Segments Precedence

> **Scope:** the four-level precedence chain:
> **exact NAS IP → segment exception range → segment CIDR base → category fallback → reject**.
> The `radius-tests/fixtures/seed_authorization_matrix.sql` provides the
> canonical fixture; this recipe is the live mirror.

## 1. Provision segments and a category

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Parent segment 10.1.0.0/16
PARENT=$(curl -sS -X POST http://localhost:8000/api/v1/network-segments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"DC-Core","cidr":"10.1.0.0/16","description":"data-center core"}' | jq -r '.id')

# Disjoint segment 10.2.0.0/16 (cannot overlap with parent)
OTHER=$(curl -sS -X POST http://localhost:8000/api/v1/network-segments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"Branch","cidr":"10.2.0.0/16","description":"branch offices"}' | jq -r '.id')

# Category
CAT=$(curl -sS -X POST http://localhost:8000/api/v1/nas-categories \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"DC-Routers","criticality":"critical","vendor":"Cisco"}' | jq -r '.id')

# NASes
curl -sS -X POST http://localhost:8000/api/v1/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"nasname\":\"10.1.5.5\",\"shortname\":\"dc-1\",\"secret\":\"s\",\"category_id\":$CAT}" | jq .
curl -sS -X POST http://localhost:8000/api/v1/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"nasname\":\"10.2.7.7\",\"shortname\":\"branch-1\",\"secret\":\"s\",\"category_id\":$CAT}" | jq .
```

## 2. Four-level assignment map

| Level | User | Target | Group |
|---|---|---|---|
| 1 (exact IP) | `dc_root` | `nas_ip = 10.1.5.5` | `L1-ExactAdmins` |
| 2 (segment exception range) | `dc_segment` | `segment_id = $PARENT`, `start = 10.1.5.10`, `end = 10.1.5.20` | `L2-RangeAdmins` |
| 3 (segment base) | `dc_segment_base` | `segment_id = $PARENT` | `L3-SegmentAdmins` |
| 4 (category fallback) | `dc_category` | `nas_category_id = $CAT` | `L4-CategoryAdmins` |

```bash
USERS=(dc_root dc_segment dc_segment_base dc_category)
GROUPS=(L1-ExactAdmins L2-RangeAdmins L3-SegmentAdmins L4-CategoryAdmins)

# L1 — exact IP
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"dc_root","nas_ip":"10.1.5.5","radius_group":"L1-ExactAdmins","justification":"L1","approved_by":"admin","is_active":true}' > /dev/null

# L2 — segment exception range
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"username\":\"dc_segment\",\"segment_id\":$PARENT,\"target_start_ip\":\"10.1.5.10\",\"target_end_ip\":\"10.1.5.20\",\"radius_group\":\"L2-RangeAdmins\",\"justification\":\"L2\",\"approved_by\":\"admin\",\"is_active\":true}" > /dev/null

# L3 — segment base
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"username\":\"dc_segment_base\",\"segment_id\":$PARENT,\"radius_group\":\"L3-SegmentAdmins\",\"justification\":\"L3\",\"approved_by\":\"admin\",\"is_active\":true}" > /dev/null

# L4 — category fallback
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"username\":\"dc_category\",\"nas_category_id\":$CAT,\"radius_group\":\"L4-CategoryAdmins\",\"justification\":\"L4\",\"approved_by\":\"admin\",\"is_active\":true}" > /dev/null
```

## 3. Validate with `/preview` (no UDP)

```bash
# (1) exact-IP user authenticating against 10.1.5.5
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"dc_root","nas_ip":"10.1.5.5"}' \
  | jq '.resolution_path, .mapping.radius_group'

# (2) range user authenticating against 10.1.5.15 (inside range)
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"dc_segment","nas_ip":"10.1.5.15"}' \
  | jq '.resolution_path, .mapping.radius_group'

# (3) base user authenticating against 10.1.99.99 (in segment, no exception hit)
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"dc_segment_base","nas_ip":"10.1.99.99"}' \
  | jq '.resolution_path, .mapping.radius_group'

# (4) category user authenticating against 10.2.7.7 (no IP, no segment match → category fallback)
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"dc_category","nas_ip":"10.2.7.7"}' \
  | jq '.resolution_path, .mapping.radius_group'
```

**Expected `resolution_path`:**
1. `"ip"` → `L1-ExactAdmins`
2. `"range"` (or `"segment"` with range hit) → `L2-RangeAdmins`
3. `"segment"` → `L3-SegmentAdmins`
4. `"category"` → `L4-CategoryAdmins`

## 4. Validate with RADIUS

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
    VALUES ('dc_root','Cleartext-Password',':=','pw'),
           ('dc_segment','Cleartext-Password',':=','pw'),
           ('dc_segment_base','Cleartext-Password',':=','pw'),
           ('dc_category','Cleartext-Password',':=','pw');
  INSERT INTO radusergroup (username, groupname) VALUES
    ('dc_root', 'L1-ExactAdmins'),
    ('dc_segment', 'L2-RangeAdmins'),
    ('dc_segment_base', 'L3-SegmentAdmins'),
    ('dc_category', 'L4-CategoryAdmins');
"

for pair in "dc_root:10.1.5.5" "dc_segment:10.1.5.15" "dc_segment_base:10.1.99.99" "dc_category:10.2.7.7"; do
  user="${pair%:*}"; ip="${pair#*:}"
  docker exec radius-server bash -c "radtest $user pw $ip 10 s 0 127.0.0.1"
done
```

**Expected:** four `Access-Accept` replies, each returning the matching
group's `Reply-Message`.

## 5. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Preview returns `none` for level 1 | Exact IP rule missing; another rule is shadowing it | Drop older rules with same priority |
| Preview returns the wrong level | Priority ordering not preserved across rows | Lower priority number → wins |
| `radius rejects` all levels | The `nas_based_authorization` policy is not active | `/radius-tests/conftest.py` precondition probe — see [`radius-tests/README.md`](../../../radius-tests/README.md#probe-of-precondition-active-wiring) |

## 6. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username LIKE 'dc_%';
  DELETE FROM radusergroup WHERE username LIKE 'dc_%';
"
TOKEN=...
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/access-policies/assignments" \
  | jq -r '.[] | select(.username|startswith("dc_")) | .id' \
  | xargs -I {} curl -sS -X DELETE \
    -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/access-policies/assignments/{}"
```

## Cross-references

- **Precedence chain spec:** [`docs/modules/access-policies.md` § 4](../modules/access-policies.md#4-precedence--priority--fallback-chain)
- **Network Segments module:** [`docs/modules/network-segments.md`](../modules/network-segments.md)
- **NAS Categories module:** [`docs/modules/nas-categories.md`](../modules/nas-categories.md)
- **Matrix seed fixture:** [`radius-tests/fixtures/seed_authorization_matrix.sql`](../../../radius-tests/fixtures/seed_authorization_matrix.sql)
