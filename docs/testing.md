---
goal: Document the layered testing strategy and the deterministic commands an AI agent can run to execute any layer, including environment-dependent fallback rules.
audience: agent + human
prerequisites:
  - Repository cloned and dependencies installed
  - Python ≥ 3.11, Node ≥ 18, optional Docker for heavy layers
inputs:
  - .env.test (optional, copied from .env.test.example)
outputs:
  - Test pass/fail status per layer; coverage deltas; exit code 0
---

# Testing Strategy

ZeroRadius uses a four-layer pyramid. Each layer is independent; the only
shared assumption is that the source code under test is the same.

```
        ┌─────────────────────┐
        │  E2E (Playwright)   │  ← slowest, full stack, real browser
        ├─────────────────────┤
        │  RADIUS (pyrad)     │  ← protocol-level, needs FreeRADIUS server
        ├─────────────────────┤
        │  Backend (pytest)   │  ← fast, in-memory SQLite, httpx
        ├─────────────────────┤
        │  Frontend (Vitest)  │  ← fast, jsdom, MSW v2
        └─────────────────────┘
```

## Quick reference

| Layer | When to run | Command | Skipped when… |
|---|---|---|---|
| **All fast (default)** | Before any commit | `./scripts/test-all.sh` | never |
| Frontend fast | After changing `frontend/src/` | `./scripts/test-frontend-fast.sh` | never |
| Backend fast | After changing `backend/app/` | `./scripts/test-backend-fast.sh` | never |
| RADIUS | After changing `radius/`, `radius-tests/`, FreeRADIUS policy | `./scripts/test-all.sh --full` | FreeRADIUS unreachable (test is skipped, not failed) |
| E2E | Before releases, after major flows | `./scripts/test-all.sh --e2e` | no running frontend + backend |
| Full pyramid | Pre-release | `./scripts/test-all.sh --full` | — |

## Orchestrator: `test-all.sh`

```bash
./scripts/test-all.sh                       # fast only
./scripts/test-all.sh --full                # fast + docker + radius + e2e
./scripts/test-all.sh --radius              # fast + radius
./scripts/test-all.sh --e2e                 # fast + e2e
./scripts/test-all.sh --with-docker --e2e   # docker stack + e2e
./scripts/test-all.sh --full --continue-on-failure
./scripts/test-all.sh --full --no-cleanup   # leave docker stack up
./scripts/test-all.sh --no-fast --with-docker
```

**Exit codes:**
- `0` — all passed
- `1` — one or more failed
- `2` — invalid args or pre-flight failure

`--with-docker` starts the compose test stack but does **not** run any tests; combine it with `--radius`, `--e2e`, or `--full` to actually execute against the stack.

## 1. Frontend — Vitest

```bash
./scripts/test-frontend-fast.sh
```

**What it does:**
- Uses local `frontend/node_modules` (no Docker).
- Invokes Vitest via Windows-safe `cmd /c vitest.cmd` wrapper or direct binary on POSIX.
- Non-watch mode (`run`).
- Exits with the test result code.

**Manual invocation:**

```bash
# POSIX (macOS, Linux, WSL)
./scripts/test-frontend-fast.sh

# Windows CMD / PowerShell
cmd /c "frontend\node_modules\.bin\vitest.cmd run"
```

**Expected output:** `Test Files  N passed (N)` + a coverage table when thresholds trigger.

**Configuration:** `frontend/vitest.config.js`. Mocks live in `frontend/src/test/mocks/handlers.js`.

## 2. Backend — pytest

```bash
./scripts/test-backend-fast.sh
```

**What it does:**
- Activates `backend/.venv` (POSIX `bin/activate`, Windows `Scripts/activate`).
- Loads `.env.test.example` defaults; overlays `.env.test` if present.
- Runs `python -m pytest -m "not radius and not infra"` (skip heavy layers).
- Coverage enforced via `--cov-fail-under=59` in `backend/pytest.ini`.
- Pass `--no-cov` to skip coverage for max speed.

**Manual invocation:**

```bash
# POSIX
./scripts/test-backend-fast.sh
# or, with venv active:
python -m pytest tests/ -v -m "not radius and not infra"

# Windows
.venv\Scripts\activate.bat
python -m pytest tests/ -v -m "not radius and not infra"
```

**Expected output:** `N passed in Xs` plus a coverage summary table.

**Configuration:** `backend/pytest.ini`, `backend/conftest.py`.

### Markers

| Marker | Skipped by fast suite? | Marker purpose |
|---|---|---|
| (default) | included | Unit + integration tests against SQLite |
| `@pytest.mark.radius` | **yes** | Requires a running FreeRADIUS server (see §3) |
| `@pytest.mark.infra` | **yes** | Requires certificates / Docker / Linux-specific setup |

Run only one marker:

```bash
cd backend
python -m pytest -m "not radius" -v           # everything except pyrad
python -m pytest -m radius -v                 # only pyrad
python -m pytest -m "infra" -v                # only certificate/Docker tests
```

### Test taxonomy

```
backend/tests/
├── unit/                # service-level unit tests (no FastAPI client)
│   ├── test_auth_service.py
│   ├── test_bandwidth_profiles.py
│   ├── test_cert_init.py
│   ├── test_db_exceptions.py
│   ├── test_dictionary_loader.py
│   ├── test_groups_service.py
│   ├── test_integrity.py
│   ├── test_lockout.py
│   ├── test_models_regression_parity.py
│   ├── test_network_segment_fix.py
│   ├── test_regression_sqlite_foreign_keys.py
│   ├── test_schema_sync.py
│   ├── test_schema_validator.py
│   └── test_vsa_guard.py
├── integration/         # FastAPI AsyncClient + httpx + SQLite
│   ├── (read-write CRUD per router)
│   ├── test_jit.py
│   ├── test_circuits.py
│   ├── test_circuits_resolve.py
│   └── test_security_*.py  # A01–A10 threat regression tests
└── (no separate e2e here — e2e is Playwright in /e2e/)
```

### Conventions

- Use `python -m pytest`, never bare `pytest` (Windows compatibility).
- Use `@pytest.mark.radius` / `infra` for environment-dependent tests.

## 3. RADIUS — pyrad

```bash
cd radius-tests
python -m pytest -v -m radius
```

**Status:** infrastructure in place; run only when FreeRADIUS is reachable at
`$RADIUS_HOST:$RADIUS_PORT` (default `localhost:1812`).

**Environment variables:**

| Variable | Default | Purpose |
|---|---|---|
| `RADIUS_HOST` | `127.0.0.1` | FreeRADIUS host |
| `RADIUS_PORT` | `1812` | Auth port |
| `RADIUS_SECRET` | `testing123` | Shared secret |
| `RADIUS_MATRIX_PROBE_USER` | `segment_admin_a` | Precondition probe user |
| `RADIUS_MATRIX_PROBE_PASS` | `testpassword` | Probe password |
| `RADIUS_MATRIX_PROBE_NAS_IP` | `192.168.10.50` | Probe NAS-IP for exact-match test |

**Probe of precondition (`radius_policy_precondition` fixture):**

1. Server unreachable / timeout → `pytest.skip` (skipped, not failed).
2. Server reachable but marker / CIR not present → `pytest.fail("nas_based_authorization disabled or seed missing")`.
3. Server + wiring + seed OK → matrix runs.

This avoids false positives when FreeRADIUS responds but isn't running
`nas_based_authorization`.

**Test files:**

```
radius-tests/
├── conftest.py                          # fixtures
├── test_radius_auth.py                  # basic Access-Accept/Reject
├── test_radius_vsa.py                   # Cisco AVPair validation
├── test_radius_mac_priority.py          # Cambium AP proxy baseline
├── test_radius_network_segments.py      # matrix deterministic
├── test_radius_preconditions.py         # wiring probe
├── test_radius_vendor_scenarios.py      # Cisco WLC, Dahua CCTV, Proxy-MAC, generic IP
├── fixtures/seed_authorization_matrix.sql
└── README.md
```

## 4. E2E — Playwright

```bash
cd e2e
npx playwright test                # headless
npx playwright test --ui           # debug UI
```

**Prereqs:**
- Frontend on `http://localhost:5173` (Vite dev) or `http://localhost:3009` (Docker).
- Backend on `http://localhost:8000` (default mode) or `http://localhost:8001` (Docker test stack — requires `frontend/vite.config.js` proxy target update per [`docs/testing.md` → §4 Mode 2](#mode-2--docker-test-stack)).

### Mode 1 — Fast local (default)
- Backend on `localhost:8000` (dev with `.venv`).
- Vite proxy (`vite.config.js`) routes `/api` → `localhost:8000`.

### Mode 2 — Docker test stack
- Backend on `localhost:8001` (from `docker-compose.test.yml`).
- Edit `frontend/vite.config.js` to proxy `/api` → `localhost:8001` (the only supported way; no `VITE_API_URL` env var exists).

### Install Playwright browsers (one-time)

```bash
npx playwright install
```

**Test files:**

```
e2e/tests/
├── login.spec.js
├── policies.spec.js
├── rbac-ui.spec.js
└── users-crud.spec.js
```

## 5. Docker Compose test stack

```bash
docker compose -f docker-compose.test.yml up -d      # start
docker compose -f docker-compose.test.yml ps         # wait for healthy
# run tests
docker compose -f docker-compose.test.yml down -v    # teardown (drops volume)
```

**Includes:** test-db (3307), test-radius (1812/udp, 1813/udp), test-backend (8001).

**Test env vars** (set in `docker-compose.test.yml`):

| Variable | Value |
|---|---|
| `DATABASE_URL` | `mysql+aiomysql://test_user:test_password@test-db/zeroradius_test` |
| `RADIUS_HOST` | `test-radius` |
| `RADIUS_PORT` | `1812` |
| `RADIUS_SECRET` | `testing123` |
| `SECRET_KEY` | `test-secret-key-not-for-production-use-32chars` |

## 6. CI / Heavy Tests — Planned

Containerised Playwright + GitHub Actions workflow + reporting. Until
landed, run the pyramid locally before tagging a release.

## 7. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `bash: pytest: command not found` | Wrong shell invocation | Use `python -m pytest …` |
| `database is locked` | SQLite file lock left from a hung prior run | `rm backend/test.db backend/.coverage*` (the SQLite file is gitignored) |
| RADIUS tests fail with connection refused | FreeRADIUS not running | `docker compose up radius-server -d` |
| RADIUS tests skip (env OK but matrix fails) | `nas_based_authorization` disabled or seed missing | Apply `radius-tests/fixtures/seed_authorization_matrix.sql` |
| Vitest output stalls on Windows | PowerShell execution policy | Use `cmd /c "vitest.cmd run"` or the script wrapper |
| E2E timeout | Frontend not running | `npm run dev` in `frontend/` |
| `403` on `/api/v1/admin/...` | Token lacks role | Re-login as superadmin |
| `coverage failed: 59` threshold | Code added without tests | Add a test or annotate with `# pragma: no cover` (rare) |

## 8. Conventions

- Always `python -m pytest`, never bare `pytest`.
- Always `cmd /c "vitest.cmd …"` on Windows for Vitest.
- RADIUS tests marked `@pytest.mark.radius`, skipped by default.
- Infra tests marked `@pytest.mark.infra`, skipped by default (certs, Docker, Linux-specific).
- Backend fast tests use in-memory SQLite — no external DB needed.
- Frontend tests use MSW v2 — see `frontend/src/test/mocks/`.

## 9. Cross-references

- **Deployment:** [`docs/deployment.md`](deployment.md)
- **Architecture:** [`docs/architecture.md`](architecture.md)
- **Security tests:** [`docs/security-coverage.md`](security-coverage.md)
- **RADIUS protocol:** [`docs/architecture.md` → §2.2 NAC → RADIUS](architecture.md#22-nac--radius-authentication)
