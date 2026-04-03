# ZeroRadius — Exportación de Memoria Engram

Fecha: 2026-04-03

## Sesiones

- **zeroradius** (2026-04-03 04:42:43) — 0 observations
- **zeroradius** (2026-04-02 15:16:46) — 0 observations
- **zeroradius** (2026-04-01 22:16:54) — 0 observations
- **zeroradius** (2026-04-01 21:45:20) — 0 observations
- **zeroradius** (2026-03-30 22:04:14) — 6 observations

## Observaciones

### #270 [session_summary] — Session summary: zeroradius
## Goal
Cerrar el branch `fix/docker-restart-policy-v2` con commit y PR a main para la política de restart de Docker.

## Discoveries
- El repo no tiene labels `type:*` — usa los labels nativos de GitHub (`bug`, `enhancement`, etc.)
- El PR fue creado correctamente como #10 vinculado al issue #9 (`status:approved`)

## Accomplished
- ✅ Commit: `fix(docker): add restart unless-stopped policy to all services` (978a29d)
- ✅ Push de `fix/docker-restart-policy-v2` a origin
- ✅ PR #10 creado en GitHub contra `main`, cierra issue #9, label `bug`

## Next Steps
- Revisar checks automáticos en el PR #10
- Hacer merge cuando los checks pasen
- Sincronizar el servidor Ubuntu de pruebas con el docker-compose actualizado

## Relevant Files
- `docker-compose.yml` — `restart: unless-stopped` en los 4 servicios (db, backend, frontend, freeradius)
- `.gitignore` — excluye carpetas de configuración de agentes AI

---

### #289 [session_summary] — Session summary: zeroradius
## Goal
Write integration tests for the NAS Categories feature and Privilege Map updates in the backend.

## Accomplished
- ✅ Created `backend/tests/integration/test_nas_categories.py` covering CRUD and RBAC for NAS categories.
- ✅ Created `backend/tests/integration/test_privilege_map.py` covering Privilege Map Bulk IP and new Category-based mapping.
- ✅ Fixed `python-multipart` installation issue in the testing environment.
- ✅ Fixed a bug in `backend/app/routers/nas_categories.py` where `model_dump()` returned `datetime` objects instead of strings, causing a JSON serialization error in `audit.py`. Added `mode="json"`.
- ✅ Fixed test endpoint URLs to match actual router prefixes (`/nas-categories` instead of `/api/nas-categories`).
- ✅ Passed `test_schema_sync.py` and all 16 integration tests.

## Discoveries
- Integration tests should NOT prefix URLs with `/api/` unless it's configured in `main.py`. The routers themselves prefix endpoints.
- Pydantic's `model_dump()` returns native Python types (like `datetime`). When saving these payloads to audit logs, `model_dump(mode="json")` must be used to ensure valid JSON serialization.

## Relevant Files
- `backend/tests/integration/test_nas_categories.py` — New tests
- `backend/tests/integration/test_privilege_map.py` — New tests
- `backend/app/routers/nas_categories.py` — Fixed `model_dump(mode="json")`

---

### #290 [session_summary] — Session summary: zeroradius
## Goal
Cerrar el feature de NAS Categories (categorías dinámicas para los dispositivos de red). Ya teníamos la implementación en backend y frontend lista, por lo que el objetivo principal fue escribir las pruebas de integración (backend) y unitarias (frontend), y solucionar bugs encontrados.

## Discoveries
- Encontramos un bug de serialización JSON en el router de `nas_categories.py`: Pydantic devolvía objetos `datetime` nativos al llamar a `.model_dump()`, lo que provocaba una excepción (`TypeError: Object of type datetime is not JSON serializable`) al intentar guardar los logs de auditoría en la tabla `app_audit_log`. Se corrigió usando `.model_dump(mode="json")`.
- En los tests de integración con `httpx.AsyncClient` + routers individuales, descubrimos que no se debe prefijar las URLs con `/api/` en los tests (ej. es `/nas-categories` en vez de `/api/nas-categories`).

## Accomplished
- ✅ Escritos los tests de integración en `backend/tests/integration/test_nas_categories.py` cubriendo RBAC, creación y borrado.
- ✅ Escritos los tests de integración en `backend/tests/integration/test_privilege_map.py` verificando la lógica de IP vs. Categoría.
- ✅ Se corrió el test de sincronización de esquema (`test_schema_sync.py`) validando las migraciones.
- ✅ Corregido el bug de serialización JSON de Pydantic.
- 🔲 Quedó pendiente la ejecución final exitosa de los tests de frontend (Vitest) en `frontend/src/test/NASPage.test.jsx`, ya que hubo interrupciones leyendo los resultados del segundo agente.

## Relevant Files
- `backend/app/routers/nas_categories.py` — Se fixeo el guardado de auditoría (`.model_dump(mode="json")`).
- `backend/tests/integration/test_nas_categories.py` — Nuevos tests de integración.
- `backend/tests/integration/test_privilege_map.py` — Tests de nueva lógica IP/Categoría.
- `frontend/src/test/NASPage.test.jsx` — Tests de frontend para la UI del nuevo feature.

---

### #291 [discovery] — Fixed: RADIUS listening on external interfaces
**What**: Investigated why eapol_test was failing with "Connection refused" - found RADIUS IS listening on external interfaces (0.0.0.0:1812), connectivity works (UDP port open), but logs show "unknown client 192.168.1.37"

**Why**: Previous session claimed NAS was added to database, but current state shows it's missing. The database must not have been properly committed or the container was rebuilt without that data.

**Where**: 
- Server 192.168.1.35 running RADIUS with `network_mode: host`
- FreeRADIUS listening on 0.0.0.0:1812 (correct)
- Test server 192.168.1.37 can reach port 1812 (verified with nc)

**Learned**: The "unknown client" error means the NAS is not in the 'nas' table, not a network/port issue. Need to add NAS entry with secret 'testing123' to the database, then reload/restart RADIUS container.

---

### #292 [bugfix] — EAP-TTLS completamente funcional — Access-Accept confirmado
**What**: EAP-TTLS end-to-end funciona completamente. Access-Accept confirmado con TLS 1.2 (ECDHE-RSA-AES256-GCM-SHA384), certificado ZeroRadius-CA validado, Phase 2 PAP exitoso.

**Why**: Objetivo del proyecto — autenticar equipos Cambium PMP 450i via RADIUS con EAP-TTLS.

**Where**: 
- Cliente: 192.168.1.37 (eapol_test)
- Servidor RADIUS: 192.168.1.35 (FreeRADIUS en Docker)
- TLS cipher: ECDHE-RSA-AES256-GCM-SHA384

**Learned**: 
- La cadena completa de fixes fue: (1) private_key_file → server.key, (2) PKI regenerada con CA:FALSE en server cert, (3) volumen certs montado directo en /etc/freeradius/certs, (4) usuario en radcheck, (5) NAS en nas table
- Todos los cambios están commiteados en main (commits e93518b, db28864, 102aeec)
- El setup es reproducible — no hay cambios manuales sin commitear

---
