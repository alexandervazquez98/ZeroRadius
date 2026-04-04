# ZeroRadius — Layered Testing Strategy

This document describes the testing pyramid for ZeroRadius and the official
commands to run each layer.

## Test Layers

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

## Quick Reference

| Layer | When to run | Command |
|-------|-------------|---------|
| **All fast (default)** | Before any commit | `./scripts/test-all.sh` |
| Frontend fast | After changing `frontend/src/` | `./scripts/test-frontend-fast.sh` |
| Backend fast | After changing `backend/app/` | `./scripts/test-backend-fast.sh` |
| Docker test env | For integration/RADIUS/E2E tests | `docker compose -f docker-compose.test.yml up -d` |
| RADIUS | After changing RADIUS config or `radius-tests/` | See § RADIUS Tests |
| E2E | Before releases, after major flows | See § E2E Tests |
| Full pyramid | Pre-release, heavy validation | `./scripts/test-all.sh --full` |

## Orchestrator: `test-all.sh`

The recommended entry point for running tests is `./scripts/test-all.sh`.
It orchestrates the entire test pyramid with sensible defaults and opt-in
heavy layers.

```bash
# Default: fast local only (backend + frontend)
./scripts/test-all.sh

# Full pyramid: fast + docker + radius + e2e
./scripts/test-all.sh --full

# Selective layers
./scripts/test-all.sh --radius              # fast + RADIUS
./scripts/test-all.sh --e2e                 # fast + E2E
./scripts/test-all.sh --with-docker --e2e   # docker stack + E2E

# Control flow
./scripts/test-all.sh --full --continue-on-failure  # don't stop on first failure
./scripts/test-all.sh --full --no-cleanup           # keep Docker stack up after
./scripts/test-all.sh --no-fast --with-docker       # skip fast, only docker
```

**Exit codes:** `0` = all passed, `1` = one or more failed, `2` = invalid args or pre-flight failure.

**Important:** `--with-docker` only starts the Docker Compose test stack. It does **not** run any tests by itself. You must combine it with `--radius`, `--e2e`, or `--full` to actually execute tests against the stack.

Run `./scripts/test-all.sh --help` for the full flag reference.

---

## 1. Frontend Fast Tests (Vitest)

Runs component and unit tests in jsdom with MSW v2 for API mocking.

```bash
./scripts/test-frontend-fast.sh
```

**What it does:**
- Uses local `frontend/node_modules` (no Docker)
- Invokes Vitest via the Windows-safe `cmd /c` wrapper
- Runs in non-watch mode (`run`)
- Exits with the test result code

**Manual invocation:**

```bash
# From project root (Git Bash / WSL / Linux):
./scripts/test-frontend-fast.sh

# From project root (PowerShell / CMD):
cmd /c "frontend\node_modules\.bin\vitest.cmd run"

# From frontend directory (Git Bash / WSL / Linux / macOS):
cd frontend && cmd /c "node_modules\.bin\vitest.cmd run"
```

**Note:** Avoid `npm run test` on Windows PowerShell — it may fail due to execution policy restrictions. Use the `cmd /c` wrapper or the repo script instead.

**Configuration:** `frontend/vitest.config.js`

---

## 2. Backend Fast Tests (pytest)

Runs unit and integration tests using an in-memory SQLite database.
RADIUS-dependent tests are excluded by default.

```bash
./scripts/test-backend-fast.sh
```

**What it does:**
- Activates `backend/.venv` (project virtualenv) — handles both Unix (`bin/activate`) and Windows (`Scripts/activate`) paths
- Loads `.env.test.example` defaults, then overlays `.env.test` if present
- Runs `python -m pytest` with `-m "not radius and not infra"` to skip heavy RADIUS and infrastructure tests
- Coverage is enabled by default (enforced by `--cov-fail-under=59` in `pytest.ini`)
- Pass `--no-cov` to the script for maximum speed: `./scripts/test-backend-fast.sh --no-cov`

**Manual invocation:**

```bash
# From project root (Git Bash / WSL / Linux):
./scripts/test-backend-fast.sh

# From backend directory (with .venv activated):
# Unix/Git Bash: source .venv/bin/activate
# Windows CMD:  .venv\Scripts\activate.bat
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pytest tests/ -v -m "not radius and not infra"

# Without coverage for maximum speed:
python -m pytest tests/ -v -m "not radius and not infra" --no-cov
```

**Configuration:** `backend/pytest.ini`, `backend/conftest.py`

**Test environment defaults:** See `.env.test.example` at repo root.

---

## 3. RADIUS Tests (pyrad) — Available (environment-dependent)

Protocol-level tests that communicate with a real FreeRADIUS server.

**Status:** Infrastructure in place. Requires a live FreeRADIUS server to run.

**Prerequisites:**
- FreeRADIUS server running on `localhost:1812` (env var: `RADIUS_PORT`, default `1812`)
- `pyrad` installed in the test environment
- RADIUS shared secret configured (`RADIUS_SECRET`)

**Manual invocation:**

```bash
cd radius-tests
python -m pytest . -v -m radius
```

---

## 4. E2E Tests (Playwright) — Available (environment-dependent)

Full browser tests that exercise the complete stack (frontend + backend + DB).

**Status:** Specs and config exist; requires both frontend and backend running.

**Prerequisites:**
- Frontend serving on `localhost:5173`
- Backend API running — see two modes below:

**Mode 1 — Fast local (default):**
- Backend on `localhost:8000` (local dev with `.venv`)
- Vite proxy (`vite.config.js`) routes `/api` → `localhost:8000` automatically
- No extra configuration needed

**Mode 2 — Docker test stack:**
- Backend on `localhost:8001` (from `docker-compose.test.yml`)
- Change proxy target in `frontend/vite.config.js` from `8000` to `8001`
  (this is the **only** supported way — there is no `VITE_API_URL` env var in the frontend codebase)

- Playwright browsers installed (`npx playwright install`)

**Manual invocation:**

```bash
cd e2e
npx playwright test

# Debug with UI:
npx playwright test --ui
```

---

## 5. Docker Compose Test Stack

A dedicated Docker Compose stack (`docker-compose.test.yml`) that spins up an
isolated, ephemeral environment for integration, RADIUS, and E2E testing.

**What it includes:**
- MariaDB on port `3307` (no persistent volume — clean slate each run)
- FreeRADIUS on ports `1812/1813` (debug mode enabled)
- Backend API on port `8001` (test configuration)

**Usage:**

```bash
# Start the test environment
docker compose -f docker-compose.test.yml up -d

# Wait for all services to be healthy
docker compose -f docker-compose.test.yml ps

# Run tests against the test environment
# (configure your test runner to target localhost:8001, localhost:3307, etc.)

# Tear down — -v removes the ephemeral database
docker compose -f docker-compose.test.yml down -v
```

**Test environment variables:**
| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `mysql+aiomysql://test_user:test_password@test-db/zeroradius_test` |
| `RADIUS_HOST` | `test-radius` |
| `RADIUS_PORT` | `1812` |
| `RADIUS_SECRET` | `testing123` |
| `SECRET_KEY` | test-only value (not for production) |

---

## 6. CI / Heavy Tests — Planned

Full CI pipeline wiring with Playwright headless E2E tests in a containerized
environment.

**Planned scope:**
- Playwright container for headless E2E
- GitHub Actions workflow
- Test result reporting and coverage thresholds

---

## Test Environment Configuration

### `.env.test` (optional)

Copy `.env.test.example` to `.env.test` at the repo root if you need to
override test defaults. The backend fast-test script will source it
automatically.

```bash
cp .env.test.example .env.test
# Edit .env.test as needed
```

**Note:** `.env.test` is gitignored. Only `.env.test.example` is tracked.

---

## Conventions

- **Always use `python -m pytest`**, never `pytest` directly (Windows compatibility)
- **Always use `cmd /c "vitest.cmd ..."`** on Windows for Vitest (PowerShell execution policy)
- **RADIUS tests are marked** with `@pytest.mark.radius` and excluded by default
- **Infrastructure tests are marked** with `@pytest.mark.infra` and excluded by default (certs, Docker, Linux-specific)
- **Backend tests use in-memory SQLite** — no external DB needed for fast tests
- **Frontend tests use MSW v2** for API mocking — see `frontend/src/test/mocks/`
