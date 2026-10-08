---
goal: Document every supported ZeroRadius deployment variant and the operational levers (env vars, secrets, certs, troubleshooting) needed to keep them healthy.
audience: agent + human
prerequisites:
  - Docker Engine ≥ 24 + Compose v2
  - For Linux override: Linux kernel with support for `network_mode: host`
inputs:
  - .env at the project root
  - certs/ at the project root for TLS
  - host bind ports: 3009, 443, 1812/udp, 1813/udp, 514/udp
outputs:
  - All 5 containers `healthy`
  - GET http://localhost:8000/health → 200
---

# Deployment

> Everything here is reproducible. There are no undocumented environment
> variables. If you encounter one, it is a bug — file an issue.

## 1. Three compose files

| File | Purpose | Use it when |
|---|---|---|
| `docker-compose.yml` | Production-style stack (5 containers, persistent DB, host-binding 3009/443/1812/1813/514) | Production deployment or full local dev |
| `docker-compose.test.yml` | Ephemeral test stack (no DB volume, 8001 backend, 3307 DB, ephemeral secrets) | Running integration / RADIUS / e2e tests |
| `docker-compose.linux.yml` | Override on top of `docker-compose.yml`: enables `network_mode: host` for the radius container, opens 127.0.0.1:3306 | Linux host where you want the RADIUS container to see host loopback |

Linux variant is auto-selected by `scripts/start.sh` on Linux.

## 2. Environment variables (canonical list)

> These are the **only** variables the backend reads. Everything else can be
> ignored; legacy or unused names are not tolerated.

| Variable | Purpose | Where it surfaces |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | MariaDB root password | `docker-compose.yml` → `db` service |
| `MYSQL_DATABASE` | MariaDB database name (e.g. `radius`) | `db` + everything connecting to it |
| `MYSQL_USER` | Application DB user | `db` grants + backend DSN |
| `MYSQL_PASSWORD` | Application DB password | `db` grants + backend DSN |
| `RADIUS_SECRET` | Shared secret for the `radius-server` container (used by `clients.conf`) | `radius/clients.conf` template |
| `SECRET_KEY` | JWT signing key. **Backend crashes at startup if unset.** Generate with `openssl rand -hex 32`. | `app/core/security.py` |
| `ALGORITHM` | JWT algorithm (`HS256`/`HS384`/`HS512` default `HS256`) | same |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token TTL (default `30`) | same |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins (no trailing slash) | `app/main.py` |
| `SYSLOG_API_KEY` | Header sent by the `radius-syslog` container on `POST /syslog/ingest` | `docker-compose.yml` → `syslog.service.api_key` (default `syslog-secret-key` if unset) |
| `DISABLE_DOCS` | When `true` removes Swagger/ReDoc | `app/main.py` |

### Non-secret test variables (`.env.test.example`)

`DATABASE_URL`, `TEST_DATABASE_URL`, `RADIUS_HOST`, `RADIUS_PORT` are read by
the **test harness only**; the production backend ignores them.

### Generating secrets

```bash
openssl rand -hex 32             # SECRET_KEY
openssl rand -hex 16             # MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD, SYSLOG_API_KEY
```

## 3. Bring-up

### 3.1 First-time install

```bash
git clone https://github.com/alexandervazquez98/ZeroRadius.git
cd ZeroRadius
cp .env.example .env
$EDITOR .env                      # fill secrets
docker compose up -d --build
docker compose ps --format json | jq -r '(.Services // .[]) | .Service + "\t" + .Health'
docker exec -it radius-backend python -m scripts.seed_admin \
    --username admin --password "$(openssl rand -hex 12)"
```

### 3.2 Stack variants

```bash
# Production-style main stack (5 containers, persistent volume)
docker compose up -d --build

# Linux networking override (host net on radius)
docker compose -f docker-compose.yml -f docker-compose.linux.yml up -d --build

# Ephemeral test stack
docker compose -f docker-compose.test.yml up -d --build

# Tear down
docker compose down                 # preserves db_data
docker compose down -v              # destroys db_data too
```

`scripts/start.sh` wraps the Linux variant detection.

## 4. TLS / certificates

| Mount | Source | Purpose |
|---|---|---|
| `./radius/certs/` → `/etc/freeradius/certs` | in-repo (regenerated on `docker compose up`) | Self-signed CA + server cert + DH params (FreeRADIUS EAP) |
| `./radius/certs/` → `/app/radius-certs` | same | Backend can serve the CA cert for download (`/nas` shows the CA URL) |
| `./certs/` → `/etc/nginx/certs` | user-supplied | TLS cert + key for the frontend Nginx |

Frontend certs are **not** generated automatically. To enable HTTPS on
`https://localhost` and `https://<your-host>`:

```bash
mkdir -p certs
# Self-signed for dev:
openssl req -x509 -newkey rsa:4096 -nodes -sha256 \
    -keyout certs/server.key -out certs/server.crt \
    -days 365 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

For production, replace with Let's Encrypt or your CA's certs.

## 5. Backend admin bootstrap

After the stack is healthy, the first superadmin must be seeded:

```bash
docker exec -it radius-backend python -m scripts.seed_admin \
    --username admin \
    --password "<your-strong-bootstrap-password>"
```

The first login will be forced into a password change.

To skip seeding (when an admin already exists or for CI), skip the step; the
backend will still start, you just won't be able to log in without an admin
account.

## 6. Operations

### 6.1 Health checks

| Service | Endpoint / command |
|---|---|
| `db` | `mysqladmin ping` inside the container (10s interval) |
| `radius` | `freeradius` process check via `healthcheck` (varies by stack) |
| `backend` | `python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"` (10s interval) |
| `syslog` | no explicit healthcheck; observed via log volume |
| `frontend` | no explicit healthcheck; observed via `nginx -t` |

Outside Docker:

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/health/containers   # admin only
curl -sS http://localhost:8000/health/resources    # admin only
```

### 6.2 Logs

```bash
docker compose logs -f --tail=200 backend
docker compose logs -f --tail=200 radius | grep -E 'Access-(Accept|Reject) Id'
docker exec radius-server tail -F /var/log/freeradius/radius.log
```

### 6.3 Backups

```bash
# DB dump
docker exec radius-db mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" \
    --single-transaction --routines --triggers \
    "$MYSQL_DATABASE" > backup-$(date +%F).sql

# Volume snap (alternative)
docker run --rm -v zeroradius_db_data:/data -v "$PWD":/backup \
    alpine tar -czf /backup/db_data-$(date +%F).tgz /data
```

### 6.4 Upgrades

```bash
git pull
docker compose build --pull              # rebuild with latest base images
docker compose up -d                     # rolling restart
docker exec radius-backend python -m scripts.alembic upgrade head   # if migrations need to run
docker exec radius-backend python -m scripts.seed_admin --check   # confirm admin still exists
```

The Alembic chain is idempotent; **never** edit migrations that have been
applied to a deployed environment.

### 6.5 Rotating secrets

`SECRET_KEY` rotation invalidates **all** existing JWTs; users must log in again.

```bash
NEW_SECRET=$(openssl rand -hex 32)
sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET|" .env
unset NEW_SECRET
docker compose up -d backend              # rolling restart
```

## 7. Security implications

- **`/var/run/docker.sock` is mounted into `radius-backend`.** This is required
  for the WebSocket Live Log Viewer (`/system/logs/stream`), which reads
  `radius-server` container stdout via the Docker SDK. Treat the backend
  process as root-equivalent inside the stack. If you cannot accept this:
  run the backend out-of-band and remove that mount; the viewer endpoint
  will return 503.
- **`DISABLE_DOCS=true`** removes `/docs` and `/redoc` from the prod build.
  Always set this in production.
- **`ALLOWED_ORIGINS`** must list the exact origin(s) used by the frontend
  (including the scheme). `*` is not supported.
- **`SYSLOG_API_KEY`** is shared between `rsyslog/Dockerfile` env and the
  backend (`app/services/syslog_integrity.py`). Rotating requires
  redeploying both containers in step.
- The first-login password change is enforced by
  `app/middleware/force_password_change.py`. Admins with
  `force_password_change=1` are redirected to `/change-password`.

## 8. Troubleshooting

| Symptom | First check | Doc |
|---|---|---|
| `db` reports `starting` for > 30 s | `docker compose logs db` for `permission denied` on volume mount; check `db_data` volume | — |
| `backend` reports `unhealthy` after start | `docker compose logs backend`; check `SECRET_KEY` is set and ≥ 32 chars | [`docs/security-coverage.md`](security-coverage.md#a04-auth) |
| `radius` exits immediately | `docker compose logs radius`; usually a TLS or rlm_sql config; check `radius/certs/` is populated | [`docs/architecture.md` → data flow](architecture.md#22-nac--radius-authentication) |
| Login returns 401 with correct creds | Check `app_audit_log` for the failure reason; verify `SECRET_KEY` did not change mid-session | [`docs/security-coverage.md`](security-coverage.md#a04-auth) |
| Live log viewer shows nothing | Backend cannot reach Docker daemon (volume mount issue); verify `/var/run/docker.sock` is the host socket | [`docs/04-live-log-viewer.md`](04-live-log-viewer.md#architecture) |
| `radtest` returns no reply | `docker compose ps` for radius; `docker compose logs radius` for "Ready to process requests" | [`docs/simulation/01-basic-access-request.md`](simulation/01-basic-access-request.md) |
| Syslog forwarded but no rows in `syslog_events` | Compare `SYSLOG_API_KEY` between `.env` and the running container; if they diverged after a `.env` edit, recreate the syslog container | [`docs/deployment.md` → rotating secrets](#6-rotating-secrets) |
| `pytest` reports `database is locked` | You're running backend-fast and a previous run aborted; SQLite file lock left behind | [`docs/testing.md`](testing.md#troubleshooting) |
| FreeRADIUS config check fails on Linux | `docker compose -f docker-compose.yml -f docker-compose.linux.yml config` to validate the override parses | — |

## 9. Where to look next

- **Testing the deployment:** [`docs/testing.md`](testing.md)
- **Database migrations:** [`docs/database.md`](database.md#alembic-migration-history)
- **Architecture detail:** [`docs/architecture.md`](architecture.md)
- **Security threat model:** [`docs/security-coverage.md`](security-coverage.md)
