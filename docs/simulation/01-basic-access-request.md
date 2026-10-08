---
goal: Confirm a NAS already registered in the system can authenticate a user with a valid RADIUS group and produce `Access-Accept`; the same NAS with a user not in any group produces `Access-Reject`.
audience: agent + human
prerequisites:
  - Healthy stack from [`docs/00-agent-quickstart.md`](../00-agent-quickstart.md)
  - Admin JWT
  - At least one NAS registered (the recipe shows how)
  - At least one RADIUS group with `Cleartext-Password` reply attribute
inputs:
  - One new user record in `radcheck`
  - One group record in `radgroupreply`
outputs:
  - `Access-Accept` for the happy path
  - `Access-Reject` for the unmatched path
backout: deletes the seeded user / group / NAS
---

# Simulation 01 — Basic Access-Request

> **Scope:** single NAS IP, no Access Policy involvement yet — direct
> `SQL-Group` authentication against a group that allows the user.

## 1. Provision the dependencies

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# 1. NAS — the agent will authenticate against this
curl -sS -X POST http://localhost:8000/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nasname":"192.168.99.10","shortname":"sim-nas","secret":"test-secret"}' | jq .

# 2. RADIUS group — has the password check attribute
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radgroupreply (groupname, attribute, op, value)
  VALUES ('Sim-Group', 'Reply-Message', ':=', 'Welcome, simulator');
"

# 3. User — Cleartext-Password in radcheck, mapped to Sim-Group in radusergroup
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
  VALUES ('simuser', 'Cleartext-Password', ':=', 'simpass');
  INSERT INTO radusergroup (username, groupname, priority)
  VALUES ('simuser', 'Sim-Group', 0);
"
```

## 2. Happy path — `Access-Accept`

```bash
docker exec radius-server bash -c '
  radtest simuser simpass 192.168.99.10 10 test-secret 0 127.0.0.1
'
```

**Expected output (excerpt):**

```
Sent Access-Request Id N from 0.0.0.0:... to 192.168.99.10:1812
   User-Name = "simuser"
   User-Password = "simpass"
   NAS-IP-Address = 127.0.0.1
Received Access-Accept Id N from 192.168.99.10:1812
   Reply-Message = "Welcome, simulator"
```

## 3. Reject path — wrong password

```bash
docker exec radius-server bash -c '
  radtest simuser wrong-pass 192.168.99.10 10 test-secret 0 127.0.0.1
'
```

**Expected output (excerpt):**

```
Received Access-Reject Id N from 192.168.99.10:1812
```

## 4. Reject path — user not in any group

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
  VALUES ('orphan', 'Cleartext-Password', ':=', 'orphanpass');
"
docker exec radius-server bash -c '
  radtest orphan orphanpass 192.168.99.10 10 test-secret 0 127.0.0.1
'
```

**Expected output:** `Access-Reject` because `orphan` has no `radusergroup`
row. The RADIUS layer sees no `SQL-Group` to hydrate.

## 5. Validate via the audit trail

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/audit/access?nas_ip=192.168.99.10&limit=5" | jq '.[].reply | {reply, username}'
```

**Expected output:** at least three entries: `Access-Accept`, `Access-Reject`, `Access-Reject`.

## 6. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| No reply from FreeRADIUS | `radius-server` container not running | `docker compose up -d radius` |
| Access-Accept always returned | The `nas_based_authorization` policy may have a default-allow rule; check the policy file | [`docs/architecture.md` § 4](../architecture.md#4-process-level-integration) |
| `radpostauth` not updated | Container doesn't use the `rlm_sql` post-auth module | Check `radius/sql` mount and policy logs |
| Reply-Message missing | Group not properly registered in `radgroupreply` | `SELECT * FROM radgroupreply WHERE groupname='Sim-Group'` |

## 7. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username IN ('simuser', 'orphan');
  DELETE FROM radusergroup WHERE username IN ('simuser', 'orphan');
  DELETE FROM radgroupreply WHERE groupname='Sim-Group';
"
NAS_ID=$(curl -sS -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/nas?search=sim-nas" | jq -r '.[0].id')
[ -n "$NAS_ID" ] && curl -sS -X DELETE \
  -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/nas/$NAS_ID"
```

## Cross-references

- **Architecture / auth flow:** [`docs/architecture.md` § 2.2](../architecture.md#22-nac--radius-authentication)
- **Audit access log:** [`docs/modules/audit.md`](../modules/audit.md#22-get-auditaccess)
- **JIT Break-Glass:** [`docs/simulation/07-jit-break-glass.md`](07-jit-break-glass.md)
