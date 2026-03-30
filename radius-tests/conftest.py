"""
conftest.py para radius-tests — fixtures de pyrad.

Fixtures:
- radius_client: instancia de pyrad.Client apuntando al servidor FreeRADIUS de test.
- skip_if_no_radius: skipea el test si el servidor no responde en el timeout.

Configuración via variables de entorno:
  RADIUS_HOST  (default: 127.0.0.1)
  RADIUS_PORT  (default: 1812)
  RADIUS_SECRET (default: testing123)
"""

import os
import socket

import pytest
from pyrad.client import Client
from pyrad.dictionary import Dictionary

# ---------------------------------------------------------------------------
# Configuración del servidor RADIUS de test (puede sobreescribirse con env vars)
# ---------------------------------------------------------------------------

RADIUS_HOST = os.getenv("RADIUS_HOST", "127.0.0.1")
RADIUS_PORT = int(os.getenv("RADIUS_PORT", "1812"))
RADIUS_SECRET = os.getenv("RADIUS_SECRET", "testing123").encode()

# Path al diccionario RADIUS estándar (instalado junto con pyrad)
_DICT_PATH = os.path.join(os.path.dirname(__file__), "dictionary")


def _server_is_reachable(host: str, port: int, timeout: float = 1.0) -> bool:
    """Intenta conectar por UDP al servidor RADIUS. Retorna True si hay algo escuchando."""
    # pyrad usa UDP — hardcode el socket type
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        # Enviamos un byte vacío; si no hay error de red, asumimos que el host es alcanzable.
        sock.sendto(b"\x00", (host, port))
        sock.close()
        return True
    except (OSError, socket.error):
        return False


@pytest.fixture(scope="session")
def radius_dict() -> Dictionary:
    """Carga el diccionario RADIUS. Usa el built-in de pyrad si no hay uno local."""
    import pyrad.dictionary as _pd
    import importlib.resources as _res

    # pyrad incluye su propio dictionary por defecto
    dict_path = os.path.join(os.path.dirname(_pd.__file__), "dictionary")
    if not os.path.exists(dict_path):
        # Fallback: crear un diccionario vacío mínimo
        dict_path = None  # type: ignore[assignment]

    return Dictionary(dict_path)


@pytest.fixture(scope="session")
def radius_client(radius_dict: Dictionary) -> Client:
    """
    Cliente pyrad pre-configurado para el servidor FreeRADIUS de test.

    No verifica que el servidor esté disponible — eso lo hace skip_if_no_radius.
    """
    client = Client(
        server=RADIUS_HOST,
        authport=RADIUS_PORT,
        secret=RADIUS_SECRET,
        dict=radius_dict,
    )
    client.timeout = 3
    client.retries = 1
    return client


@pytest.fixture(autouse=False)
def skip_if_no_radius():
    """
    Fixture que skipea el test si el servidor RADIUS no está disponible.

    Usar como parámetro en tests que requieren FreeRADIUS:
        def test_foo(radius_client, skip_if_no_radius): ...

    O marcar el test con @pytest.mark.radius y agregar este fixture.
    """
    if not _server_is_reachable(RADIUS_HOST, RADIUS_PORT):
        pytest.skip(
            f"FreeRADIUS server not reachable at {RADIUS_HOST}:{RADIUS_PORT}. "
            "Run with Docker: see radius-tests/README.md"
        )
