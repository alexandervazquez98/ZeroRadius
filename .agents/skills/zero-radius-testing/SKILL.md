---
name: zero-radius-testing
description: >
  Patrones, convenciones y gotchas para el entorno de testing completo de ZeroRadius.
  Cubre backend (pytest + integration + unit), RADIUS (pyrad), frontend (Vitest + MSW v2) y E2E (Playwright).
  Trigger: Cuando se escriben, modifican o ejecutan tests en ZeroRadius — en cualquier capa.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Cuándo usar esta skill

- Al agregar tests de backend (integration o unit) en `backend/tests/`
- Al agregar tests RADIUS en `radius-tests/`
- Al agregar component tests en `frontend/src/test/`
- Al agregar E2E specs en `e2e/tests/`
- Al ejecutar la suite completa o diagnosticar fallos
- Al ajustar coverage thresholds o markers de pytest

---

## Arquitectura del entorno de testing

```
proyecto/
├── backend/
│   ├── pytest.ini                    # config markers + threshold
│   ├── requirements-test.txt         # pyrad, pytest-playwright, etc.
│   └── tests/
│       ├── conftest.py               # scope=session, superadmin seed
│       ├── integration/              # HTTP tests por router
│       └── unit/                     # lógica de negocio aislada
├── radius-tests/                     # tests de protocolo RADIUS con pyrad
│   ├── conftest.py
│   ├── test_radius_auth.py
│   ├── test_radius_vsa.py
│   └── README.md
├── frontend/
│   └── src/test/
│       ├── setup.js                  # MSW lifecycle (beforeAll/afterEach/afterAll)
│       ├── mocks/
│       │   ├── handlers.js           # MSW v2 — handlers centralizados
│       │   └── server.js             # setupServer(handlers)
│       ├── LoginPage.test.jsx
│       ├── UsersPage.test.jsx
│       └── GroupsPage.test.jsx
└── e2e/                              # Playwright — paquete independiente
    ├── package.json
    ├── playwright.config.js          # baseURL: localhost:5173
    └── tests/
        ├── login.spec.js
        ├── rbac-ui.spec.js
        └── users-crud.spec.js
```

---

## Comandos de ejecución

### Backend (pytest)

```powershell
# SIEMPRE usar python -m pytest, nunca "pytest" directo en Windows
# pytest no está en el PATH — el PATH no registra el binario correctamente

cd backend
python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Sin RADIUS (saltear tests de pyrad)
python -m pytest tests/ -v -m "not radius"

# Solo integration
python -m pytest tests/integration/ -v

# Solo unit
python -m pytest tests/unit/ -v
```

### RADIUS tests (pyrad)

```powershell
# Se skipean automáticamente si no hay FreeRADIUS disponible
# Requieren server FreeRADIUS corriendo en localhost:1812

cd radius-tests
python -m pytest . -v -m radius
```

### Frontend (Vitest)

```powershell
# NUNCA usar "npm run test" en PowerShell — los scripts PS1 están bloqueados por policy
# NUNCA usar "node node_modules/.bin/vitest" — es un bash script, no funciona en Windows

# Alternativa correcta:
cd frontend
cmd /c "node_modules\.bin\vitest.cmd run"

# Con coverage:
cmd /c "node_modules\.bin\vitest.cmd run --coverage"
```

### E2E (Playwright)

```powershell
# Requiere frontend en :5173 Y backend en :8000 corriendo simultáneamente
# Este es el único caso donde necesitás dos procesos activos

cd e2e
npx playwright test

# Debug con UI:
npx playwright test --ui

# Un spec específico:
npx playwright test tests/login.spec.js
```

---

## Patrones críticos

### Backend: conftest.py con scope=session

```python
# NO romper la estructura scope=session — funciona bien
# El seed usa credenciales fijas:
# usuario: test_superadmin
# password: TestPassword1!

@pytest.fixture(scope="session")
def client():
    # setup con las credenciales de seed
    ...
```

### RADIUS: marker para skipear en CI sin server

```ini
# backend/pytest.ini
[pytest]
markers =
    radius: requires FreeRADIUS server running
addopts = --cov-fail-under=59
```

```python
# En cada test de pyrad:
@pytest.mark.radius
def test_radius_auth():
    ...
```

### MSW v2 — sintaxis correcta (NO v1)

```js
// ✅ v2 — usar http y HttpResponse de "msw"
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/users', () => {
    return HttpResponse.json({ users: [] })
  }),
  http.post('/api/auth/login', () => {
    return HttpResponse.json({ access_token: 'fake-token' })
  }),
]

// ❌ NUNCA usar rest de MSW v1:
// import { rest } from 'msw'
// rest.get('/api/users', (req, res, ctx) => res(ctx.json(...)))
```

### MSW setup.js — lifecycle correcto

```js
// frontend/src/test/setup.js
import { server } from './mocks/server'
import '@testing-library/jest-dom'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### AuthProvider en tests — evitar localStorage

```jsx
// AuthProvider acepta "initialToken" prop para testing
// No necesitás mockear localStorage ni el sistema de auth real

render(
  <AuthProvider initialToken="fake-token">
    <ComponentBajoTest />
  </AuthProvider>
)
```

### GroupsPage — es un wrapper de PoliciesPage

```js
// GroupsPage carga TODOS estos endpoints — todos necesitan handler MSW:
// GET /api/groups/list
// GET /api/groups/check
// GET /api/groups/reply
// GET /api/nas
// GET /api/dictionary/attributes

// Si falta alguno de estos handlers, el test falla silenciosamente
// con errores de red que parecen de rendering
```

### NasCreate — validación de secret

```python
# El schema valida secret mínimo de 32 caracteres
# Tests que crean NAS DEBEN usar:
"shared_secret": "a" * 32  # o cualquier string de 32+ chars
```

---

## Coverage thresholds

El coverage real del proyecto es **59.43%** (estado al 2026-03-29).

Módulos sin cobertura (bajo):
- `dictionary_loader.py` — 34%
- `integrity.py` — 35%
- `ntp_status.py` — 36%
- `privilege_map.py` — 38%

```ini
# backend/pytest.ini — NO subir este threshold sin agregar tests primero
addopts = --cov-fail-under=59
```

---

## Decisiones de arquitectura

| Decisión | Motivo |
|----------|--------|
| `e2e/` como paquete independiente | Playwright requiere su propio `package.json` separado del frontend |
| `radius-tests/` fuera de `backend/tests/` | Los tests de protocolo son blackbox — no dependen del código Python |
| MSW handlers centralizados en `mocks/handlers.js` | Un solo lugar para mantener; todos los component tests los reusan |
| `scope=session` en conftest backend | Evita recrear DB en cada test — 10x más rápido |
| `cmd /c` para Vitest en PowerShell | PowerShell bloquea ejecución de `.ps1` scripts (política de seguridad) |

---

## Diagnóstico de fallos comunes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| `pytest: command not found` | PATH no registra el binario | Usar `python -m pytest` |
| `vitest: File not found` | bash script en Windows | Usar `cmd /c "node_modules\.bin\vitest.cmd run"` |
| Component test falla con errores de red | Handler MSW faltante | Agregar el endpoint a `handlers.js` |
| GroupsPage test falla aunque renderiza | Falta uno de los 5 endpoints de groups | Ver sección GroupsPage arriba |
| RADIUS test pasa en local, falla en CI | No hay FreeRADIUS en CI | Verificar mark `@pytest.mark.radius` |
| `--cov-fail-under` bloquea CI | Coverage bajó del threshold | Agregar tests O bajar threshold temporalmente |
| E2E: `net::ERR_CONNECTION_REFUSED` | Frontend/backend no están corriendo | Levantar ambos antes de `npx playwright test` |
| `act(...)` warnings en RTL | Expected noise de React 18 | Ignorar — no son failures reales |

---

## Archivos clave de referencia

- `backend/pytest.ini` — markers, threshold, addopts
- `backend/requirements-test.txt` — dependencias (pyrad==2.4, pytest-playwright==0.5.0)
- `backend/tests/conftest.py` — scope=session, credenciales seed
- `frontend/src/test/mocks/handlers.js` — MSW handlers centralizados
- `frontend/src/test/setup.js` — lifecycle MSW
- `e2e/playwright.config.js` — baseURL, timeouts
- `radius-tests/README.md` — prerequisitos para correr tests RADIUS
