---
goal: Reconcile what `/access-policies/preview` returns against what FreeRADIUS actually decides for the same `(username, nas_ip)` tuple, proving the two read the same `access_policy_assignments`.
audience: agent + human
prerequisites:
  - One NAS at `192.168.50.1`
  - Two Access Policy assignments for the same user — one with `nas_ip`, one with `segment_id` overlapping the NAS-IP
inputs:
  - `nas = 192.168.50.1`
  - `segment = 192.168.50.0/24` (containing the NAS)
  - Two assignments for user `recon_user`:
    - `A_ip` → `nas_ip = 192.168.50.1` → group `Group-IP`
    - `A_seg` → `segment_id = $SEG` → group `Group-Seg`
outputs:
  - FreeRADIUS returns `Group-IP` reply attrs (exact IP wins over segment base)
  - `/preview` agrees
backout: drops assignments + segment + NAS
---

# Simulation 05 — Access Policies Resolution (preview vs FreeRADIUS)

> **Scope:** make `/access-policies/preview` and live FreeRADIUS agree.
> This is the highest-leverage simulation for catching schema vs policy
> desyncs.

## 1. Provision

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Segment 192.168.50.0/24
SEG=$(curl -sS -X POST http://localhost:8000/api/v1/network-segments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"ReconSegment","cidr":"192.168.50.0/24"}' | jq -r '.id')

# NAS at .50.1 inside the segment
curl -sS -X POST http://localhost:8000/api/v1/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nasname":"192.168.50.1","shortname":"recon","secret":"rs"}' > /dev/null

# Two Access Policy assignments, both active, for the same user
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"recon_user","nas_ip":"192.168.50.1","radius_group":"Group-IP","justification":"ip rule","approved_by":"admin","is_active":true}' > /dev/null

curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"username\":\"recon_user\",\"segment_id\":$SEG,\"radius_group\":\"Group-Seg\",\"justification\":\"seg rule\",\"approved_by\":\"admin\",\"is_active\":true}" > /dev/null

# Seeded groups
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
    VALUES ('recon_user','Cleartext-Password',':=','reconpw');
  INSERT INTO radusergroup (username, groupname) VALUES ('recon_user','Group-IP');
  INSERT INTO radgroupreply (groupname, attribute, op, value)
    VALUES ('Group-IP','Reply-Message',':=','From exact-IP rule'),
           ('Group-Seg','Reply-Message',':=','From segment rule');
"
```

## 2. Ask the API

```bash
curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"username":"recon_user","nas_ip":"192.168.50.1"}' \
  | jq '.resolution_path, .mapping.radius_group'
```

**Expected:** `resolution_path = "ip"`, `radius_group = "Group-IP"`.

## 3. Ask FreeRADIUS

```bash
docker exec radius-server bash -c '
  radtest recon_user reconpw 192.168.50.1 10 rs 0 127.0.0.1
'
```

**Expected output (excerpt):**

```
Received Access-Accept Id N from 192.168.50.1:1812
   Reply-Message = "From exact-IP rule"
```

## 4. Cross-check agreement

| Source | Path | Group |
|---|---|---|
| `/preview` | `ip` | `Group-IP` |
| FreeRADIUS reply attribute | (Access-Accept) | `From exact-IP rule` |

If they disagree, the recipe is broken — **do not deploy**.

## 5. Failure modes / divergence patterns

| Divergence | Likely cause |
|---|---|
| `/preview` says `ip`, RADIUS says `segment` | A second exact-IP assignment was created with higher priority after the seed |
| Both say `segment` | The IP assignment was deactivated / deleted |
| RADIUS `Access-Reject`, `/preview` `ip` | Group has no `radgroupreply` rows; FreeRADIUS rejects; `/preview` doesn't see the group-reply step |
| `nas_based_authorization disabled or seed missing` | The FreeRADIUS policy is not loaded |

## 6. Cross-validation shortcut

For 100-row operations, batch the API call and the FreeRADIUS replay with a
shell loop:

```bash
USERS=(recon_user)   # add more
NASES=(192.168.50.1)

for u in "${USERS[@]}"; do
  for n in "${NASES[@]}"; do
    echo "[preview] $u @ $n"
    curl -sS -X POST http://localhost:8000/api/v1/access-policies/preview \
      -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      -d "{\"username\":\"$u\",\"nas_ip\":\"$n\"}" \
      | jq -r '"group=" + (.mapping.radius_group // "none")'
    echo "[radius ] $u @ $n"
    docker exec radius-server bash -c "radtest $u ${u}pw $n 10 rs 0 127.0.0.1" 2>&1 | grep -E "Accept|Reject"
  done
done
```

## 7. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username='recon_user';
  DELETE FROM radusergroup WHERE username='recon_user';
  DELETE FROM radgroupreply WHERE groupname IN ('Group-IP','Group-Seg');
"
TOKEN=...
AIDS=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/access-policies/assignments" \
  | jq -r '.[] | select(.username=="recon_user") | .id')
for id in $AIDS; do
  curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
    "http://localhost:8000/api/v1/access-policies/assignments/$id"
done
# (segment + NAS kept if used by other recipes; remove manually otherwise)
```

## Cross-references

- **Resolution algorithm:** [`docs/modules/access-policies.md` § 4](../modules/access-policies.md#4-precedence--priority--fallback-chain)
- **Related simulations:** [`docs/simulation/04-network-segments-precedence.md`](04-network-segments-precedence.md), [`docs/simulation/06-circuits-and-bandwidth.md`](06-circuits-and-bandwidth.md)
