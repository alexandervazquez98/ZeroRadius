# RADIUS Protocol Tests

Tests de simulación del protocolo RADIUS usando **pyrad**. Verifican autenticación Access-Request/Accept/Reject y VSA handling a nivel UDP.

## Prerrequisitos

- Python 3.11+
- Docker (para levantar FreeRADIUS de prueba)

## Instalación

```bash
cd radius-tests/
pip install -r requirements.txt
```

## Levantar FreeRADIUS con Docker

Los tests requieren un servidor FreeRADIUS corriendo con los usuarios de test configurados.

### Opción A — Docker compose del proyecto (recomendado)

El proyecto ya tiene un `docker-compose.yml` en la raíz. Asegurate de que el servicio `radius-server` esté activo:

```bash
# Desde la raíz del proyecto
docker compose up radius-server -d
```

### Opción B — FreeRADIUS standalone para tests

```bash
docker run -d \
  --name freeradius-test \
  -p 1812:1812/udp \
  -p 1813:1813/udp \
  -e TESTING=yes \
  freeradius/freeradius-server:3.2
```

Luego configurar usuarios de test en el contenedor:

```bash
docker exec freeradius-test bash -c "echo 'testuser Cleartext-Password := \"testpassword\"' >> /etc/freeradius/3.0/mods-config/files/authorize"
docker restart freeradius-test
```

### Verificar que el servidor está listo

```bash
# Desde el host (requiere freeradius-utils)
radtest testuser testpassword 127.0.0.1 0 testing123

# Output esperado:
# Sent Access-Request Id 1 from 0.0.0.0:... to 127.0.0.1:1812
# Received Access-Accept Id 1 from 127.0.0.1:1812
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `RADIUS_HOST` | `127.0.0.1` | IP del servidor FreeRADIUS |
| `RADIUS_PORT` | `1812` | Puerto UDP de autenticación |
| `RADIUS_SECRET` | `testing123` | Shared secret del NAS de test |
| `RADIUS_MATRIX_PROBE_USER` | `segment_admin_a` | Usuario de precondición para validar wiring de `nas_based_authorization` |
| `RADIUS_MATRIX_PROBE_PASS` | `testpassword` | Password del usuario de precondición |
| `RADIUS_MATRIX_PROBE_NAS_IP` | `192.168.10.50` | NAS-IP del probe que debe resolver por regla exacta |

```bash
# Ejemplo con servidor remoto
RADIUS_HOST=192.168.1.100 RADIUS_SECRET=mysecret pytest radius-tests/
```

## Ejecutar los tests

```bash
# Todos los tests RADIUS (requiere servidor activo)
pytest radius-tests/ -v

# Solo tests de autenticación básica
pytest radius-tests/test_radius_auth.py -v

# Solo tests de VSA
pytest radius-tests/test_radius_vsa.py -v

# Matriz determinística segment/CIDR/CIR
cd radius-tests
python -m pytest -m radius test_radius_network_segments.py -v
```

## Seed determinístico de autorización

La matriz de precedencia/CIR usa un seed explícito en:

`radius-tests/fixtures/seed_authorization_matrix.sql`

Objetos esperados por el probe y la suite:

- Usuarios: `segment_admin_a`, `segment_reader_b`
- Marcadores de regla ganadora: `MATRIX-EXACT-*`, `MATRIX-RANGE-*`, `MATRIX-BASE-*`, `MATRIX-FALLBACK-*`
- CIR (Access-Accept): `Cambium-Canopy-HPDLCIR`, `Cambium-Canopy-HPULCIR`

La fixture `authorization_matrix_seed` valida que ese contrato exista antes de correr la matriz.
Si falta algún objeto en el SQL, la suite falla en setup (fail fast).

## Probe de precondición (wiring activo)

La fixture `radius_policy_precondition` diferencia tres casos:

1. **Servidor inalcanzable / timeout** → `pytest.skip` (infra no disponible)
2. **Servidor reachable pero sin marker/CIR esperado** → `pytest.fail("nas_based_authorization disabled or seed missing")`
3. **Servidor + wiring + seed OK** → ejecuta la matriz de precedencia

Esto evita falsos verdes cuando FreeRADIUS responde, pero no está ejecutando `nas_based_authorization`.

## Excluir tests RADIUS del suite principal

Los tests RADIUS están marcados con `@pytest.mark.radius`. Para correr el backend sin requerir FreeRADIUS:

```bash
# Desde backend/
pytest -m "not radius" -v
```

## Comportamiento cuando FreeRADIUS no está disponible

Si el servidor no responde, el fixture `skip_if_no_radius` detecta la situación y **skipea** el test automáticamente con un mensaje claro. **No falla** — solo se omite:

```
SKIPPED [1] conftest.py:XX: FreeRADIUS server not reachable at 127.0.0.1:1812.
Run with Docker: see radius-tests/README.md
```

Si el servidor responde pero no aparece el marcador/CIR esperado del probe, la matriz falla explícitamente con:

`nas_based_authorization disabled or seed missing`

## Estructura

```
radius-tests/
  conftest.py          # Fixtures: radius_client, skip_if_no_radius
  requirements.txt     # pyrad, pytest
  test_radius_auth.py  # Access-Request / Accept / Reject básico
  test_radius_vsa.py   # VSA Cisco-AVPair validation
  README.md            # Este archivo
```
