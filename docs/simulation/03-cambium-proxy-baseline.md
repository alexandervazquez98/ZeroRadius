---
goal: Validate that the `Calling-Station-Id` (MAC) is the discriminator between direct NAS-AP login and proxied-downstream-device login when the NAS-IP is the same.
audience: agent + human
prerequisites:
  - Stack healthy
  - `radius-tests/fixtures/seed_mac_priority.sql` applied
  - Both `ap_admin` and `proxied_sm` users seeded, sharing the same NAS-IP
inputs:
  - One NAS row with `nasname = 192.168.10.50`
  - Two distinct groups: `DirectAdmin` and `SMReader` with different reply attrs
outputs:
  - `ap_admin` authenticating from a "dummy MAC" (`00:00:00:00:00:00`) → `Access-Accept` + Admin reply attrs
  - `proxied_sm` authenticating with a real MAC (`0A:00:3E:12:34:56`) → `Access-Accept` + Reader reply attrs
backout: drops the seeded rows
---

# Simulation 03 — Cambium AP Proxy Baseline

> **Scope:** the **Anti-Proxy Strategy for Major NAS** described in the
> README. Same NAS-IP for an admin's direct login and a downstream SM's
> proxied login — the `Calling-Station-Id` (MAC) is the discriminator.

## 1. Apply the seed

```bash
docker exec -i radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" \
    < radius-tests/fixtures/seed_mac_priority.sql
```

Verify the fixture is in place:

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  SELECT username, groupname FROM radusergroup
  WHERE username IN ('ap_admin', 'proxied_sm');
"
```

**Expected:** two rows.

## 2. NAS

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# Register a category if missing
CATEGORY_ID=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/nas-categories | jq -r '.[] | select(.name=="WiFi-AP").id')

# Register (or update) the NAS at 192.168.10.50
curl -sS -X POST http://localhost:8000/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"nasname\":\"192.168.10.50\",\"shortname\":\"major-ap\",\"secret\":\"ap-secret\",\"category_id\":${CATEGORY_ID:-null}}" | jq .
```

## 3. Access Policies: priority chain

Create the two priority-1 and priority-2 rules the seed expects. The MAC
`00:00:00:00:00:00` is the dummy marker the README references for direct
access.

```bash
# Direct admin rule (priority 1)
curl -sS -X POST http://localhost:8000/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "username": "ap_admin",
    "nas_ip": "192.168.10.50",
    "calling_station_id": "00:00:00:00:00:00",
    "radius_group": "DirectAdmin",
    "privilege_level": 9,
    "justification": "Major-NAS admin login (dummy MAC)",
    "approved_by": "admin",
    "is_active": true
  }' | jq .

# Proxied SM rule (priority 2)
curl -sS -X POST http://localhost:8000/access-policies/assignments \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{
    "username": "proxied_sm",
    "nas_ip": "192.168.10.50",
    "calling_station_id": "0A:00:3E:12:34:56",
    "radius_group": "SMReader",
    "privilege_level": 1,
    "justification": "Proxied downstream device",
    "approved_by": "admin",
    "is_active": true
  }' | jq .
```

## 4. Direct admin authentication (dummy MAC)

```bash
docker exec radius-server bash -c '
  radtest ap_admin "adminpass!" \
    192.168.10.50 10 ap-secret 0 \
    127.0.0.1 "00:00:00:00:00:00"
'
```

**Expected:** `Received Access-Accept` with the Admin reply attributes.

## 5. Proxied SM authentication (real MAC)

```bash
docker exec radius-server bash -c '
  radtest proxied_sm "smpass!" \
    192.168.10.50 10 ap-secret 0 \
    127.0.0.1 "0A:00:3E:12:34:56"
'
```

**Expected:** `Received Access-Accept` with the Reader reply attributes.

## 6. Cross-MAC — `ap_admin` with a non-dummy MAC

```bash
docker exec radius-server bash -c '
  radtest ap_admin "adminpass!" \
    192.168.10.50 10 ap-secret 0 \
    127.0.0.1 "0A:00:3E:99:99:99"
'
```

**Expected:** `Access-Reject` (the policy requires dummy MAC for `ap_admin`).

## 7. Validate

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/audit/access?nas_ip=192.168.10.50&limit=5" \
  | jq '.[].reply | {reply, username}'
```

**Expected:** `Access-Accept`, `Access-Accept`, `Access-Reject` in order.

## 8. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| All three `Access-Reject` | Access Policy validation rejected the seeds; check `validate_category_membership` errors | `/access-policies/preview` to debug |
| Admin gets Reader attrs (priority wrong) | The two rows have equal priority; MAC tie-break not enforcing | Update priority on the rows (lower number = higher priority) |
| `sql: error` from FreeRADIUS | `rlm_sql` connection failing (DB down?) | [`docs/deployment.md` troubleshooting](../deployment.md#troubleshooting) |

## 9. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username IN ('ap_admin', 'proxied_sm');
  DELETE FROM radusergroup WHERE username IN ('ap_admin', 'proxied_sm');
  DELETE FROM radgroupreply WHERE groupname IN ('DirectAdmin', 'SMReader');
  DELETE FROM access_policy_assignments WHERE username IN ('ap_admin', 'proxied_sm');
"
# NAS itself may be retained for other simulations; remove only if needed.
```

## Cross-references

- **Anti-Proxy strategy:** [`docs/README.md`](../../README.md#advanced-anti-proxy-strategy-for-major-nas)
- **Access Policies:** [`docs/modules/access-policies.md`](../modules/access-policies.md)
- **VSA / vendor scenarios:** [`docs/simulation/02-vsa-vendor-scenarios.md`](02-vsa-vendor-scenarios.md)
