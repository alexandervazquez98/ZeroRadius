---
goal: Bring up a fully operational ZeroRadius stack in under 10 minutes and prove it with at least one RADIUS simulation, using deterministic commands an AI agent can follow verbatim.
audience: agent
prerequisites:
  - macOS, Linux, or Windows with WSL2
  - Docker Engine ≥ 24 + Docker Compose v2
  - Git
  - jq (for parsing `/health` responses)
  - ~3 GB free disk (images + DB volume)
inputs:
  - .env (copied from .env.example; populated with MYSQL_*, SECRET_KEY, SYSLOG_API_KEY)
outputs:
  - All 5 containers reporting `healthy`
  - GET /health → {"status":"ok"}
  - Login at http://localhost:3009 with bootstrap admin credentials
  - One successful `Access-Accept` against a NAS registered through the API
---

# 00. Agent Quickstart

> This document is designed for AI agents. Every command is copy-paste-able;
> every expected output is given so you can stop and ask the human only when a
> step diverges from the expected pattern.

## 1. Clone and configure

```bash
git clone https://github.com/alexandervazquez98/ZeroRadius.git
cd ZeroRadius
cp .env.example .env
```

Edit `.env` minimally (replace all `change-me` placeholders):

```bash
sed -i.bak \
    -e "s|^MYSQL_ROOT_PASSWORD=.*|MYSQL_ROOT_PASSWORD=$(openssl rand -hex 16)|" \
    -e "s|^MYSQL_PASSWORD=.*|MYSQL_PASSWORD=$(openssl rand -hex 16)|" \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
    -e "s|^SYSLOG_API_KEY=.*|SYSLOG_API_KEY=$(openssl rand -hex 16)|" \
    .env
unset MYSQL_ROOT_PASSWORD MYSQL_PASSWORD SECRET_KEY SYSLOG_API_KEY   # do not leak into shell history
```

**Expected output:** no output (silent success).
**Failure:** if `sed` fails (BSD vs GNU syntax on macOS), use `perl -pi -e 's|...|...|g' .env` instead.

## 2. Build and start the stack

```bash
docker compose up -d --build
```

Wait for healthchecks (poll until all services report `healthy`):

```bash
docker compose ps --format json | jq -r '
  (.Services // .[]) | .Service + "\t" + .Health
'
```

**Expected output** (after ≤ 60 s):

```
db         healthy
radius     healthy
backend    healthy
syslog     healthy
frontend   healthy
```

**Failure:** if `backend` reports `starting` for > 30 s, follow
[`docs/deployment.md` → "Troubleshooting"](deployment.md#troubleshooting).

## 3. Bootstrap the first superadmin

```bash
docker exec -it radius-backend python -m scripts.seed_admin \
    --username admin \
    --password "BootStrap!2026"
```

**Expected output** (verbatim):

```
SUCCESS: Superadmin 'admin' created.

NEXT STEPS:
  1. Log in with:  username=admin  password=BootStrap!2026
  2. You will be forced to change the password on first login.
  ...
```

**Failure:** if the script prints `An admin user ... already exists`, the
database is not empty — restore from a clean volume or use the existing admin.

## 4. Smoke test the API

```bash
# Health endpoint
curl -sS -o /tmp/health.json -w "%{http_code}" http://localhost:8000/health
echo   # → 200
cat /tmp/health.json | jq .   # → {"status":"ok", ...}

# Login → JWT
curl -sS -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=BootStrap!2026" | jq -r '.access_token'
```

**Expected output:** the second command prints a long JWT (dot-separated
base64 headers). Save it:

```bash
export TOKEN=$(curl -sS -X POST http://localhost:8000/auth/token \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=admin&password=BootStrap!2026" | jq -r '.access_token')
```

## 5. Register a NAC and validate

```bash
# Register a NAS (Network Access Server) we'll simulate against
curl -sS -X POST http://localhost:8000/nas \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "nasname": "192.168.99.10",
    "shortname": "sim-ap",
    "secret": "test-secret",
    "description": "agent smoke-test NAS",
    "category_id": null
  }' | jq .
```

**Expected output:** 201 with the persisted NAS object containing an `id`.

Now send a RADIUS `Access-Request` from inside the radius container (this
exercises the full SQL-driven path and the `nas_based_authorization` policy):

```bash
docker exec radius-server bash -c '
  echo "testagent Cleartext-Password := \"testsecret\"" \
    >> /etc/raddb/mods-config/files/authorize
  radiusd -C
'
```

**Expected output:** `Configuration is OK` (or final `Ready to process requests`).

```bash
docker exec radius-server bash -c '
  radtest testagent testsecret 127.0.0.1 10 test-secret 0 127.0.0.1
'
```

**Expected output (happy path):** ends with `Received Access-Accept Id <n> from 127.0.0.1:1812`.
**Expected output (if no policy attached):** `Received Access-Reject` — that is *not* a failure of the stack; it means you need to attach an Access Policy. See [`docs/modules/access-policies.md`](modules/access-policies.md) (Phase 2 — placeholder for the simulated recipe).

## 6. Run the test pyramid

Pick a layer based on what you changed:

| You changed | Command | Expected duration | Skipped when… |
|---|---|---|---|
| `backend/app/**` | `./scripts/test-backend-fast.sh` | ~30 s | never (SQLite in-memory) |
| `frontend/src/**` | `./scripts/test-frontend-fast.sh` | ~20 s | never (Vitest jsdom) |
| `radius/**`, `radius-tests/**` | `docker exec radius-server pkill -f freeradius; ./scripts/test-all.sh --full` | ~10 min | no FreeRADIUS reachable |
| Anything end-to-end | `cd e2e && npx playwright test` | ~3 min | no running stack |

The orchestrator (`./scripts/test-all.sh`) runs the full pyramid in one
command. For the test layer command reference and pytest markers, see
[`docs/testing.md`](testing.md).

## 7. Stop the stack (when done)

```bash
docker compose down            # preserve data
docker compose down -v         # destroy the volume (clean slate)
```

## Where to go next

- **Run a vendor scenario:** [`docs/simulation/02-vsa-vendor-scenarios.md`](simulation/02-vsa-vendor-scenarios.md) *(Phase 3)*
- **Modify an endpoint:** [`docs/api-reference.md`](api-reference.md) *(Phase 2)*
- **Troubleshoot:** [`docs/deployment.md` → Troubleshooting](deployment.md#troubleshooting)
- **Add a security test:** [`docs/security-coverage.md`](security-coverage.md)
- **Understand the schema:** [`docs/database.md`](database.md)

## Self-validation checklist for the agent

When you have finished this quickstart, confirm:

- [ ] `docker compose ps` shows 5 healthy containers.
- [ ] `curl http://localhost:8000/health` returns 200 with `{"status":"ok"}`.
- [ ] You obtained a non-empty JWT from `POST /auth/token`.
- [ ] `POST /nas` returned 201 with an `id`.
- [ ] At least one test layer (backend-fast minimum) returned exit code 0.

If any of the above fail, **stop and report** the exact command, exact
output, and exit code. Do not invent a workaround.
