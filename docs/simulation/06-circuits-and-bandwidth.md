---
goal: Validate that a CIR (Committed Information Rate) value set on a BandwidthProfile and linked from an AccessPolicyAssignment is honoured on `Access-Accept`.
audience: agent + human
prerequisites:
  - One user (`cir_user`), one NAS (`192.168.10.50`), one Access Policy that points to a `BandwidthProfile` via `cir_id`
inputs:
  - `BandwidthProfile(cir_premium_50m)` with `downstream_kbps=51200, upstream_kbps=25600`
  - `Circuit(circ-test)` with `circuit_id=2001, nas_ip=192.168.10.50`
  - `AccessPolicyAssignment(username=cir_user, group=cir_premium_50m, cir_id=<circuit.id>)`
outputs:
  - `Access-Accept` reply attributes include `Cambium-Canopy-HPDLCIR=51200` and `Cambium-Canopy-HPULCIR=25600` (or the configured shape)
  - `/api/v1/circuits/resolve?username=cir_user&nas_ip=192.168.10.50` returns `resolution_path: "cir"`
backout: drops circuit + assignments + profile
---

# Simulation 06 — Circuits and Bandwidth

> **Scope:** end-to-end CIR resolution. Validates the **preview** route
> (`/circuits/resolve`) and the **runtime reply attribute** are
> consistent.

## 1. Provision

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# NAS
curl -sS -X POST http://localhost:8000/api/v1/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nasname":"192.168.10.50","shortname":"cir-nas","secret":"cs"}' > /dev/null

# Bandwidth profile
curl -sS -X POST http://localhost:8000/api/v1/access-policies/bandwidth-profiles \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"cir_premium_50m","downstream_kbps":51200,"upstream_kbps":25600,"burst_allowance_kbps":8192}' > /dev/null

# Circuit
CIRCUIT=$(curl -sS -X POST http://localhost:8000/api/v1/circuits \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"circ-test","circuit_id":2001,"nas_ip":"192.168.10.50","bandwidth_down":51200,"bandwidth_up":25600}' | jq -r '.id')

# Access Policy that ties user → group → cir
curl -sS -X POST http://localhost:8000/api/v1/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"username\":\"cir_user\",\"nas_ip\":\"192.168.10.50\",\"radius_group\":\"cir_premium_50m\",\"cir_id\":$CIRCUIT,\"justification\":\"CIR demo\",\"approved_by\":\"admin\",\"is_active\":true}" > /dev/null

# Seeded user + group
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
    VALUES ('cir_user','Cleartext-Password',':=','cirpass!');
  INSERT INTO radusergroup (username, groupname) VALUES ('cir_user','cir_premium_50m');
  INSERT INTO radgroupreply (groupname, attribute, op, value)
    VALUES ('cir_premium_50m','Cambium-Canopy-HPDLCIR',':=','51200'),
           ('cir_premium_50m','Cambium-Canopy-HPULCIR',':=','25600'),
           ('cir_premium_50m','Cambium-Canopy-LPDLCIR',':=','51200'),
           ('cir_premium_50m','Cambium-Canopy-LPULCIR',':=','25600');
"
```

## 2. Preview the CIR

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/circuits/resolve?username=cir_user&nas_ip=192.168.10.50" \
  | jq '{path: .resolution_path, mapping_id: .mapping.id, profile: .profile.name, down: .profile.downstream_kbps, up: .profile.upstream_kbps}'
```

**Expected output:**

```json
{
  "path": "cir",
  "mapping_id": <integer>,
  "profile": "cir_premium_50m",
  "down": 51200,
  "up": 25600
}
```

## 3. Run FreeRADIUS

```bash
docker exec radius-server bash -c '
  radtest cir_user "cirpass!" 192.168.10.50 10 cs 0 127.0.0.1
'
```

**Expected output (excerpt):**

```
Received Access-Accept Id N from 192.168.10.50:1812
   Cambium-Canopy-HPDLCIR = 51200
   Cambium-Canopy-HPULCIR = 25600
   Cambium-Canopy-LPDLCIR = 51200
   Cambium-Canopy-LPULCIR = 25600
```

## 4. Validate

- `radpostauth.reply` row contains the CIR reply attributes.
- `/api/v1/access-policies/preview?username=cir_user&nas_ip=192.168.10.50`
  returns the same mapping.

## 5. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `/resolve` returns `path: "none"` | Access Policy missing or `cir_id` not set | Re-create with `cir_id` populated |
| `Access-Accept` but no CIR attributes | `radgroupreply` rows missing for the group | Re-run the `radgroupreply` INSERT |
| Path-ordering error on `/resolve` | `/{circuit_id}` defined before `/resolve` and `id=resolve` was matched | Already fixed in commit `77fcc8c`; verify and restart `radius-backend` |

## 6. Backout

```bash
TOKEN=...
CIR_ID=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/circuits?search=circ-test" | jq -r '.[0].id')
[ -n "$CIR_ID" ] && curl -sS -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/circuits/$CIR_ID"

# Drop access-policy + bandwidth + seeded SQL rows
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username='cir_user';
  DELETE FROM radusergroup WHERE username='cir_user';
  DELETE FROM radgroupreply WHERE groupname='cir_premium_50m';
  DELETE FROM access_policy_assignments WHERE username='cir_user';
"
curl -sS -X DELETE -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/access-policies/bandwidth-profiles/cir_premium_50m"
```

## Cross-references

- **Circuits module:** [`docs/modules/circuits.md`](../modules/circuits.md)
- **Access Policies:** [`docs/modules/access-policies.md`](../modules/access-policies.md)
- **Preview vs RADIUS reconciliation:** [`docs/simulation/05-access-policies-resolution.md`](05-access-policies-resolution.md)
