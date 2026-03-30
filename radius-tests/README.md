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
```

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

## Estructura

```
radius-tests/
  conftest.py          # Fixtures: radius_client, skip_if_no_radius
  requirements.txt     # pyrad, pytest
  test_radius_auth.py  # Access-Request / Accept / Reject básico
  test_radius_vsa.py   # VSA Cisco-AVPair validation
  README.md            # Este archivo
```
