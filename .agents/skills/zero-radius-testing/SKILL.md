---
name: zero-radius-testing
description: >
  Testing patterns, conventions, gotchas, and MANDATORY quality gates for ZeroRadius.
  Covers backend (pytest + integration + unit), RADIUS (pyrad), frontend (Vitest + MSW v2) and E2E (Playwright).
  Trigger: When writing, modifying, or executing tests in ZeroRadius — any layer.
  Also triggers AUTOMATICALLY before any git commit on feat, fix, or refactor.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "2.2"
---

## Auto-Trigger Protocol (MANDATORY)

This skill activates AUTOMATICALLY — you do NOT wait to be asked.

### When to run tests

| Trigger | Action |
|---------|--------|
| After completing a `feat`, `fix`, or `refactor` | Run the FULL relevant test suite BEFORE committing |
| After fixing a bug | Create a regression test FIRST, verify it fails on broken code, then fix, then verify it passes |
| After modifying a model or schema | Run `test_schema_sync.py` to catch model ↔ init.sql drift |
| After modifying a router/endpoint | Run integration tests for that router |
| After modifying frontend components | Run Vitest for affected component tests |
| When unsure how to run tests | Prefer the repo scripts in `scripts/` before ad-hoc commands |
| Before saying "done" / "listo" | Verify all tests pass — a task is NOT done with red tests |

### Quality gate rules

1. **NEVER commit with failing tests.** If tests fail → fix → re-run → THEN commit.
2. **NEVER skip tests silently.** If you can't run them (missing deps, no server), say so explicitly.
3. **ALWAYS report results:** X passed, Y failed, coverage %.
4. **ALWAYS create regression tests for bugs** — format: `test_regression_<bug_description>`.
5. **Schema changes require `test_schema_sync.py` to pass** — no exceptions.

### Test layer selection

**Default: Fast Local** — On the current machine (especially Windows or any host without Docker), run ONLY fast local tests. This is the default and covers the vast majority of development workflow.

**Heavy layer: Docker** — On test servers or hosts with Docker available, spin up `docker-compose.test.yml` as an ADDITIONAL layer for integration, RADIUS, and E2E tests. Docker does NOT replace fast local; it complements it.

Determine which tests to run based on what changed:

| Changed files | Tests to run |
|---------------|-------------|
| `backend/app/models/` | `./scripts/test-backend-fast.sh --no-cov tests/unit/test_schema_sync.py` |
| `backend/app/routers/` | `./scripts/test-backend-fast.sh tests/integration/` |
| `backend/app/services/` or `backend/app/core/` | `./scripts/test-backend-fast.sh tests/unit/` |
| `database/init.sql` | `./scripts/test-backend-fast.sh --no-cov tests/unit/test_schema_sync.py` |
| `frontend/src/components/` or `frontend/src/pages/` | `./scripts/test-frontend-fast.sh` |
| Multiple layers changed | `./scripts/test-all.sh` (fast local) or `./scripts/test-all.sh --full` (full pyramid) |
| RADIUS config or `radius-tests/` | Docker layer: `docker compose -f docker-compose.test.yml up -d` then `cd radius-tests && python -m pytest . -v -m radius` |
| Integration cross-service (real DB, RADIUS) | Docker layer: `docker compose -f docker-compose.test.yml up -d`, target `localhost:8001` (backend), `localhost:3307` (DB) |
| E2E (Playwright) — fast local | Frontend dev on `:5173` + backend local on `:8000` (vite proxy handles routing) |
| E2E (Playwright) — Docker stack | Frontend dev on `:5173` + backend Docker on `:8001` (change vite proxy target to `:8001` in `vite.config.js`) |
| Unsure what's affected | Start with both fast scripts, then add Docker layer if needed |

---

## When to load this skill

- When adding backend tests (integration or unit) in `backend/tests/`
- When adding RADIUS tests in `radius-tests/`
- When adding component tests in `frontend/src/test/`
- When adding E2E specs in `e2e/tests/`
- When running the full suite or diagnosing failures
- When adjusting coverage thresholds or pytest markers
- **When completing ANY code change** (auto-trigger — see protocol above)

---

## Test architecture

```
project/
├── backend/
│   ├── pytest.ini                    # config markers + threshold
│   ├── requirements-test.txt         # pyrad, pytest-playwright, etc.
│   └── tests/
│       ├── conftest.py               # scope=session, superadmin seed
│       ├── integration/              # HTTP tests per router
│       └── unit/                     # business logic isolation
├── radius-tests/                     # RADIUS protocol tests with pyrad
│   ├── conftest.py
│   ├── test_radius_auth.py
│   ├── test_radius_vsa.py
│   └── README.md
├── frontend/
│   └── src/test/
│       ├── setup.js                  # MSW lifecycle (beforeAll/afterEach/afterAll)
│       ├── mocks/
│       │   ├── handlers.js           # MSW v2 — centralized handlers
│       │   └── server.js             # setupServer(handlers)
│       ├── LoginPage.test.jsx
│       ├── UsersPage.test.jsx
│       └── GroupsPage.test.jsx
└── e2e/                              # Playwright — independent package
    ├── package.json
    ├── playwright.config.js          # baseURL: localhost:5173
    └── tests/
        ├── login.spec.js
        ├── rbac-ui.spec.js
        └── users-crud.spec.js
```

---

## Official entry points

Use these first unless you have a specific reason to drop lower-level:

- **Orchestrator (recommended):** `./scripts/test-all.sh` — runs fast local by default, opt-in heavy layers
- **Fast local (individual):** `./scripts/test-backend-fast.sh` and `./scripts/test-frontend-fast.sh`
- **Docker test stack (additional layer):** `docker compose -f docker-compose.test.yml`
- Test defaults template: `.env.test.example`
- Testing guide: `docs/testing.md`

Backend fast tests assume `backend/.venv` exists. Create it with:

```bash
cd backend
python -m venv .venv
# Unix / Git Bash:
source .venv/bin/activate
# Windows CMD:
.venv\Scripts\activate.bat
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-test.txt
```

If you need custom test env values, copy `.env.test.example` to `.env.test` at the repo root. The backend fast script auto-loads `.env.test.example` defaults and overlays `.env.test` when present.

---

## Execution commands

### Backend (pytest)

```bash
# Preferred: repo script from project root
./scripts/test-backend-fast.sh

# Fast schema sync only
./scripts/test-backend-fast.sh --no-cov tests/unit/test_schema_sync.py

# Specific backend suite
./scripts/test-backend-fast.sh tests/unit/
```

```powershell
# Manual fallback (only if you need to bypass the wrapper)
cd backend
python -m pytest tests/ -v -m "not radius and not infra"
python -m pytest tests/unit/test_schema_sync.py -v --no-cov
```

### RADIUS tests (pyrad)

```bash
# Auto-skipped if no FreeRADIUS available
# Requires FreeRADIUS server running on localhost:1812
# Env var: RADIUS_PORT (default: 1812), RADIUS_HOST (default: 127.0.0.1)

cd radius-tests
python -m pytest . -v -m radius
```

### Frontend (Vitest)

```bash
# Preferred: repo script from project root
./scripts/test-frontend-fast.sh
./scripts/test-frontend-fast.sh --coverage
```

```powershell
# Manual fallback on Windows
cd frontend
cmd /c "node_modules\.bin\vitest.cmd run"
cmd /c "node_modules\.bin\vitest.cmd run --coverage"
```

### E2E (Playwright)

E2E has TWO modes depending on where the backend is running:

```powershell
# Mode 1: Fast local — frontend on :5173 + backend on :8000 (local dev)
# Vite proxy (vite.config.js) routes /api to localhost:8000

cd e2e
npx playwright test

# Mode 2: Docker stack — frontend on :5173 + backend on :8001 (docker-compose.test.yml)
# Change vite.config.js proxy target to :8001 (only supported method)

cd e2e
npx playwright test

# Debug with UI:
npx playwright test --ui

# Specific spec:
npx playwright test tests/login.spec.js
```

---

## Docker Compose Test Stack (additional layer)

`docker-compose.test.yml` provides an isolated, ephemeral environment for
integration, RADIUS, and E2E tests. It is an **ADDITIONAL** layer — it does
not replace fast local tests.

### What it includes

| Service | Port | Notes |
|---------|------|-------|
| MariaDB | `3307` | Ephemeral — no persistent volume |
| FreeRADIUS | `1812/1813` | Debug mode (`-X`) |
| Backend API | `8001` | Test config, maps to `localhost:8001` |

### Usage

```bash
# Start the test environment
docker compose -f docker-compose.test.yml up -d

# Wait for all services to be healthy
docker compose -f docker-compose.test.yml ps

# Run tests against the test environment
# Backend integration: target localhost:8001
# RADIUS tests: cd radius-tests && python -m pytest . -v -m radius (targets localhost:1812)
# DB direct: target localhost:3307
# E2E: change vite proxy target from :8000 to :8001 in vite.config.js

# Tear down (removes ephemeral database)
docker compose -f docker-compose.test.yml down -v
```

### When to use Docker

- **Test servers / CI hosts** with Docker available: use Docker for heavy layers
- **Windows / local machine** without Docker: skip Docker, use fast local only
- Docker is **never a replacement** for fast local — always run fast local first

---

## Critical patterns

### Backend: conftest.py with scope=session

```python
# DO NOT break the scope=session structure — it works well
# Seed uses fixed credentials:
# username: test_superadmin
# password: TestPassword1!

@pytest.fixture(scope="session")
def client():
    # setup with seed credentials
    ...
```

### RADIUS: marker to skip in CI without server

```ini
# backend/pytest.ini
[pytest]
markers =
    radius: requires FreeRADIUS server running
addopts = --cov-fail-under=59
```

```python
# In each pyrad test:
@pytest.mark.radius
def test_radius_auth():
    ...
```

### MSW v2 — correct syntax (NOT v1)

```js
// ✅ v2 — use http and HttpResponse from "msw"
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json({ users: [] })
  }),
  http.post('/api/auth/login', () => {
    return HttpResponse.json({ access_token: 'fake-token' })
  }),
]

// ❌ NEVER use rest from MSW v1:
// import { rest } from 'msw'
// rest.get('/api/users', (req, res, ctx) => res(ctx.json(...)))
```

### MSW setup.js — correct lifecycle

```js
// frontend/src/test/setup.js
import { server } from './mocks/server'
import '@testing-library/jest-dom'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### AuthProvider in tests — avoid localStorage

```jsx
// AuthProvider accepts "initialToken" prop for testing
// No need to mock localStorage or the real auth system

render(
  <AuthProvider initialToken="fake-token">
    <ComponentUnderTest />
  </AuthProvider>
)
```

### ToastProvider in tests — required for pages using `useToast()`

```jsx
render(
  <ToastProvider>
    <ComponentUnderTest />
  </ToastProvider>
)
```

If the page also needs auth/query/router context, wrap `ToastProvider` inside the same render tree. Pages like `Users`, `NAS`, and `GroupsPage` now require this.

### GroupsPage — wrapper for PoliciesPage

```js
// GroupsPage loads ALL these endpoints — all need MSW handlers:
// GET /api/groups/list
// GET /api/groups/check
// GET /api/groups/reply
// GET /api/nas
// GET /api/dictionary/attributes

// If any handler is missing, the test fails silently
// with network errors that look like rendering issues
```

### NasCreate — secret validation

```python
# Schema validates minimum 32-character secret
# Tests that create NAS MUST use:
"shared_secret": "a" * 32  # or any 32+ char string
```

### Schema sync — model vs init.sql drift

```python
# backend/tests/unit/test_schema_sync.py
# Compares SQLAlchemy Base.metadata against database/init.sql DDL
# Catches missing tables and columns BEFORE deployment
# Run after ANY change to models.py or init.sql
# Has KNOWN_EXCEPTIONS dict for intentionally ORM-only columns
```

---

## Coverage thresholds

Current coverage: **59.43%** (as of 2026-03-29).

Low-coverage modules:
- `dictionary_loader.py` — 34%
- `integrity.py` — 35%
- `ntp_status.py` — 36%
- `privilege_map.py` — 38%

```ini
# backend/pytest.ini — DO NOT raise this threshold without adding tests first
addopts = --cov-fail-under=59
```

---

## Architecture decisions

| Decision | Reason |
|----------|--------|
| `e2e/` as independent package | Playwright requires its own `package.json` separate from frontend |
| `radius-tests/` outside `backend/tests/` | Protocol tests are blackbox — don't depend on Python code |
| MSW handlers centralized in `mocks/handlers.js` | Single maintenance point; all component tests reuse them |
| `scope=session` in backend conftest | Avoids recreating DB per test — 10x faster |
| `cmd /c` for Vitest on PowerShell | PowerShell blocks `.ps1` script execution (security policy) |
| `test_schema_sync.py` as unit test | No DB needed — pure structural comparison, runs in < 0.1s |

---

## Common failure diagnostics

| Symptom | Cause | Solution |
|---------|-------|----------|
| `pytest: command not found` | PATH doesn't register binary | Use `python -m pytest` |
| `backend/.venv not found` | Project virtualenv was never created | `cd backend && python -m venv .venv && pip install -r requirements.txt -r requirements-test.txt` |
| `vitest: File not found` | bash script on Windows | Use `cmd /c "node_modules\.bin\vitest.cmd run"` |
| `useToast must be used inside a ToastProvider` | Test renders a page/component that calls `useToast()` without the provider | Wrap the render tree with `ToastProvider` |
| Component test fails with network errors | Missing MSW handler | Add endpoint to `handlers.js` |
| GroupsPage test fails even though it renders | Missing one of 5 group endpoints | See GroupsPage section above |
| RADIUS test passes locally, fails in CI | No FreeRADIUS in CI | Verify `@pytest.mark.radius` marker |
| `--cov-fail-under` blocks CI | Coverage dropped below threshold | Add tests OR temporarily lower threshold |
| E2E: `net::ERR_CONNECTION_REFUSED` | Frontend/backend not running | Start both before `npx playwright test` |
| `act(...)` warnings in RTL | Expected React 18 noise | Ignore — not real failures |
| `Unknown column` in production | Model has column but init.sql doesn't | Run `test_schema_sync.py` — it catches this |

---

## Key reference files

- `backend/pytest.ini` — markers, threshold, addopts
- `backend/requirements-test.txt` — deps (pyrad==2.4, pytest-playwright==0.5.0)
- `.env.test.example` — test-only env defaults template
- `docs/testing.md` — layered testing guide and official commands
- `scripts/test-all.sh` — test pyramid orchestrator (recommended entry point)
- `scripts/test-backend-fast.sh` — official backend fast test entry point
- `scripts/test-frontend-fast.sh` — official frontend fast test entry point
- `backend/conftest.py` — scope=session, seed credentials
- `backend/tests/unit/test_schema_sync.py` — model ↔ init.sql drift detection
- `frontend/src/test/mocks/handlers.js` — centralized MSW handlers
- `frontend/src/test/setup.js` — MSW lifecycle
- `e2e/playwright.config.js` — baseURL, timeouts
- `radius-tests/README.md` — prerequisites for RADIUS tests

