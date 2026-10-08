---
goal: Validate that a JIT Break-Glass grant injects an `Expiration` attribute into `radcheck`, FreeRADIUS accepts the user during the window, and rejects after the window ends.
audience: agent + human
prerequisites:
  - Healthy stack
  - User account in `radcheck` for `jit_operator` (any baseline password)
inputs:
  - One user (`jit_operator`) with a baseline password
  - A JIT grant (`Expiration = NOW + 5 minutes`) via `/api/v1/users/jit-requests/{user}/approve`
outputs:
  - `radcheck` row with `attribute='Expiration'` for `jit_operator`
  - `radtest` → `Access-Accept` while in window
  - Manual expiry test: set `Expiration = NOW - 1 minute`; `radtest` → `Access-Reject`
backout: deletes the `Expiration` row
---

# Simulation 07 — JIT Break-Glass

> **Scope:** the `Expiration` attribute path. The exact endpoint for
> granting the JIT elevation is `POST /api/v1/users/jit-requests/{user}/approve`
> (per the workflow in [`docs/03-jit-break-glass.md`](../03-jit-break-glass.md)).
> TTL is configurable. This recipe uses a short 5-minute window for fast
> testing.

## 1. Provision the baseline user

```bash
TOKEN=$(curl -sS -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap\!2026" | jq -r '.access_token')

# A NAS is required for the simulation
curl -sS -X POST http://localhost:8000/api/v1/nas \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"nasname":"192.168.10.50","shortname":"jit-ap","secret":"js"}' > /dev/null

# Baseline user with no JIT grant yet
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  INSERT INTO radcheck (username, attribute, op, value)
    VALUES ('jit_operator','Cleartext-Password',':=','jitpass!');
"
```

## 2. Confirm baseline login

```bash
docker exec radius-server bash -c '
  radtest jit_operator jitpass! 192.168.10.50 10 js 0 127.0.0.1
'
```

**Expected:** `Access-Accept`. The user has no `Expiration` attribute yet, so
FreeRADIUS allows unconditionally.

## 3. Grant a JIT window (5 minutes)

```bash
curl -sS -X POST "http://localhost:8000/api/v1/users/jit-requests/jit_operator/approve" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"duration_minutes": 5, "justification":"agent smoke test"}' | jq .
```

**Expected:** the response confirms `Expiration` was inserted; the audit log
records the grant under `app_audit_log`.

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  SELECT * FROM radcheck WHERE username='jit_operator' AND attribute='Expiration';
"
```

**Expected:** at least one row with a future timestamp in `value`.

## 4. Confirm login still works (within window)

```bash
docker exec radius-server bash -c '
  radtest jit_operator jitpass! 192.168.10.50 10 js 0 127.0.0.1
'
```

**Expected:** `Access-Accept`.

## 5. Force-expiry — move `Expiration` into the past

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  UPDATE radcheck SET value = DATE_FORMAT(UTC_TIMESTAMP() - INTERVAL 1 MINUTE, '%b %d %Y %H:%i:%s')
  WHERE username='jit_operator' AND attribute='Expiration';
"
```

**Expected:** the user is now *outside* the JIT window.

## 6. Confirm rejection after expiry

```bash
docker exec radius-server bash -c '
  radtest jit_operator jitpass! 192.168.10.50 10 js 0 127.0.0.1
'
```

**Expected:** `Access-Reject` with `Reply-Message` mentioning expiry.

## 7. Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `Expiration` row missing after grant | Endpoint behind wrong path; check `/users/jit-requests/{user}/approve` | Verify path; check `app/routers/users.py` |
| `Access-Reject` even inside window | `Expiration` value format wrong (FreeRADIUS expects `'Mon DD YYYY HH:MM:SS'`) | Re-grant or update with `DATE_FORMAT(UTC_TIMESTAMP(), '%b %d %Y %H:%i:%s')` |
| Operator rejected with no Expiration | Lockout triggered (5 failed attempts) | `POST /api/v1/admin-users/{id}/unlock` |

## 8. Backout

```bash
docker exec radius-db mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "
  DELETE FROM radcheck WHERE username='jit_operator' AND attribute='Expiration';
"
# (leaving the baseline Cleartext-Password row in case it's reused)
```

## Cross-references

- **JIT pattern:** [`docs/03-jit-break-glass.md`](../03-jit-break-glass.md)
- **Audit log:** [`docs/modules/audit.md`](../modules/audit.md)
- **IAM removal context:** [`docs/02-iso27001-privilege-map.md` end of doc](../02-iso27001-privilege-map.md) and commit `1ce0851`
- **Basic Access-Request recipe:** [`docs/simulation/01-basic-access-request.md`](01-basic-access-request.md)
