"""Fixtures y helpers para pruebas RADIUS determinísticas."""

from dataclasses import dataclass
from pathlib import Path
import os
import select
import socket

import pytest
from pyrad import packet
from pyrad.client import Client, Timeout
from pyrad.dictionary import Dictionary

# ---------------------------------------------------------------------------
# Configuración del servidor RADIUS de test (puede sobreescribirse con env vars)
# ---------------------------------------------------------------------------

RADIUS_HOST = os.getenv("RADIUS_HOST", "127.0.0.1")
RADIUS_PORT = int(os.getenv("RADIUS_PORT", "1812"))
RADIUS_SECRET = os.getenv("RADIUS_SECRET", "testing123").encode()
SEED_SQL_PATH = Path(__file__).parent / "fixtures" / "seed_authorization_matrix.sql"
CAMBIUM_BASELINE_SEED_SQL_PATH = (
    Path(__file__).parent.parent / "seed_cambium_proxy_baseline.sql"
)

# Probe defaults (overrideables por env para entornos remotos)
PROBE_USER = os.getenv("RADIUS_MATRIX_PROBE_USER", "segment_admin_a")
PROBE_PASS = os.getenv("RADIUS_MATRIX_PROBE_PASS", "testpassword")
PROBE_NAS_IP = os.getenv("RADIUS_MATRIX_PROBE_NAS_IP", "192.168.10.50")
PROBE_MARKER = os.getenv("RADIUS_MATRIX_PROBE_MARKER", "MATRIX-EXACT-A")
PROBE_CIR_ATTRS = {
    "Cambium-Canopy-HPDLCIR": os.getenv("RADIUS_MATRIX_PROBE_HPDLCIR", "5000"),
    "Cambium-Canopy-HPULCIR": os.getenv("RADIUS_MATRIX_PROBE_HPULCIR", "2000"),
}

BASELINE_PROBE_USER = os.getenv(
    "RADIUS_BASELINE_PROBE_USER", "baseline_sm_lector_single"
)
BASELINE_PROBE_PASS = os.getenv("RADIUS_BASELINE_PROBE_PASS", "testpassword")
BASELINE_PROBE_NAS_IP = os.getenv("RADIUS_BASELINE_PROBE_NAS_IP", "192.168.88.1")
BASELINE_PROBE_CALLING_STATION_ID = os.getenv(
    "RADIUS_BASELINE_PROBE_CALLING_STATION_ID",
    "AA-BB-CC-DD-EE-FF",
)
BASELINE_PROBE_MARKER = os.getenv(
    "RADIUS_BASELINE_PROBE_MARKER",
    "BASELINE-SM-LECTOR-SINGLE",
)
BASELINE_PROBE_USERLEVEL = os.getenv("RADIUS_BASELINE_PROBE_USERLEVEL", "1")

CIR_VENDOR_KEY_ALIASES = {
    (161, 50): "Motorola-Cambium-Canopy-UserLevel",
    (161, 51): "Motorola-Cambium-Canopy-UserMode",
    (161, 200): "Cambium-Canopy-UserLevel",
    (161, 201): "Cambium-Canopy-UserMode",
    (161, 22): "Cambium-Canopy-HPDLCIR",
    (161, 23): "Cambium-Canopy-HPULCIR",
    (161, 220): "Cambium-Canopy-LPDLCIR",
    (161, 221): "Cambium-Canopy-LPULCIR",
    (161, 222): "Cambium-Canopy-HPDLCIR",
    (161, 223): "Cambium-Canopy-HPULCIR",
}

# Path al diccionario RADIUS estándar (instalado junto con pyrad)
_DICT_PATH = os.path.join(os.path.dirname(__file__), "dictionary")


@dataclass(frozen=True)
class RadiusScenario:
    username: str
    password: str
    nas_ip: str
    expected_code: int
    expected_marker: str | None
    expected_cir_attrs: dict[str, str] | None = None


def send_access_request(
    client: Client,
    username: str,
    password: str,
    nas_ip: str,
    calling_station_id: str | None = None,
    nas_port: int = 0,
):
    req = client.CreateAuthPacket(code=packet.AccessRequest, User_Name=username)
    req["User-Password"] = req.PwCrypt(password)
    req["NAS-IP-Address"] = nas_ip
    req["NAS-Port"] = nas_port
    if calling_station_id:
        req["Calling-Station-Id"] = calling_station_id
    return client.SendPacket(req)


def parse_reply_attributes(reply) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for key in reply.keys():
        normalized_key = CIR_VENDOR_KEY_ALIASES.get(key, str(key))

        try:
            values = reply[key]
        except Exception:
            continue

        if isinstance(values, (list, tuple)):
            normalized_values: list[str] = []
            for value in values:
                if normalized_key.startswith("Cambium-Canopy-") and isinstance(
                    value, (bytes, bytearray)
                ):
                    normalized_values.append(
                        str(int.from_bytes(value, byteorder="big", signed=False))
                    )
                else:
                    normalized_values.append(str(value))
            parsed[normalized_key] = normalized_values
        else:
            if normalized_key.startswith("Cambium-Canopy-") and isinstance(
                values, (bytes, bytearray)
            ):
                parsed[normalized_key] = [
                    str(int.from_bytes(values, byteorder="big", signed=False))
                ]
            else:
                parsed[normalized_key] = [str(values)]
    return parsed


def reply_contains_marker(reply, marker: str) -> bool:
    needle = marker.lower()
    attrs = parse_reply_attributes(reply)
    for values in attrs.values():
        for value in values:
            if needle in value.lower():
                return True
    return False


def assert_cir_attributes(reply, expected_cir_attrs: dict[str, str]) -> None:
    attrs = parse_reply_attributes(reply)
    for attr_name, expected_value in expected_cir_attrs.items():
        actual_values = attrs.get(attr_name)
        assert actual_values, f"Missing CIR reply attribute '{attr_name}'"
        assert expected_value in actual_values, (
            f"CIR attribute '{attr_name}' expected value '{expected_value}', got {actual_values}"
        )


def validate_policy_probe_reply(
    reply,
    expected_marker: str,
    expected_cir_attrs: dict[str, str],
) -> None:
    if reply.code != packet.AccessAccept:
        raise AssertionError(
            "nas_based_authorization disabled or seed missing "
            f"(probe expected Access-Accept, got code={reply.code})"
        )

    if not reply_contains_marker(reply, expected_marker):
        raise AssertionError("nas_based_authorization disabled or seed missing")

    assert_cir_attributes(reply, expected_cir_attrs)


def _assert_seed_contract(seed_sql: str) -> None:
    required_tokens = [
        "segment_admin_a",
        "segment_reader_b",
        "MATRIX-EXACT-A",
        "MATRIX-RANGE-A",
        "MATRIX-BASE-A",
        "MATRIX-FALLBACK-A",
        "MATRIX-RANGE-B",
        "MATRIX-BASE-B",
        "MATRIX-FALLBACK-B",
        "Cambium-Canopy-HPDLCIR",
        "Cambium-Canopy-HPULCIR",
    ]
    missing = [token for token in required_tokens if token not in seed_sql]
    assert not missing, (
        "seed_authorization_matrix.sql missing required objects: " + ", ".join(missing)
    )


def _assert_cambium_baseline_seed_contract(seed_sql: str) -> None:
    required_tokens = [
        "baseline_ap_operator",
        "baseline_sm_lector_single",
        "baseline_sm_lector_dual",
        "baseline_sm_check_reply",
        "baseline_zero_trust",
        "grp_baseline_ap_direct",
        "grp_baseline_sm_lector_single",
        "grp_baseline_sm_lector_dual",
        "grp_baseline_sm_check_reply",
        "BASELINE-AP-DIRECT",
        "BASELINE-SM-LECTOR-SINGLE",
        "BASELINE-SM-LECTOR-DUAL",
        "BASELINE-SM-CHECK-REPLY",
        "Cambium-Canopy-UserLevel",
        "Cambium-Canopy-UserMode",
        "NAS-Port",
    ]
    missing = [token for token in required_tokens if token not in seed_sql]
    assert not missing, (
        "seed_cambium_proxy_baseline.sql missing required objects: "
        + ", ".join(missing)
    )


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

    # Prefer deterministic local dictionary for cross-platform/CI compatibility
    if os.path.exists(_DICT_PATH):
        return Dictionary(_DICT_PATH)

    # Fallback: pyrad bundled dictionary (if present)
    dict_path = os.path.join(os.path.dirname(_pd.__file__), "dictionary")
    if os.path.exists(dict_path):
        return Dictionary(dict_path)

    pytest.fail("No RADIUS dictionary available (local nor pyrad bundled)")


@pytest.fixture(scope="session")
def radius_client(radius_dict: Dictionary) -> Client:
    """
    Cliente pyrad pre-configurado para el servidor FreeRADIUS de test.

    No verifica que el servidor esté disponible — eso lo hace skip_if_no_radius.
    """
    if not hasattr(select, "poll"):
        pytest.skip(
            "pyrad requires select.poll(), unavailable on this platform/runtime"
        )

    client = Client(
        server=RADIUS_HOST,
        authport=RADIUS_PORT,
        secret=RADIUS_SECRET,
        dict=radius_dict,
    )
    client.timeout = 3
    client.retries = 1
    return client


@pytest.fixture(scope="session", autouse=False)
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


@pytest.fixture(scope="session")
def authorization_matrix_seed_path() -> Path:
    if not SEED_SQL_PATH.exists():
        pytest.fail(f"Missing deterministic seed file: {SEED_SQL_PATH}")
    return SEED_SQL_PATH


@pytest.fixture(scope="session")
def authorization_matrix_seed(authorization_matrix_seed_path: Path) -> str:
    seed_sql = authorization_matrix_seed_path.read_text(encoding="utf-8")
    _assert_seed_contract(seed_sql)
    return seed_sql


@pytest.fixture(scope="session")
def cambium_proxy_baseline_seed_path() -> Path:
    if not CAMBIUM_BASELINE_SEED_SQL_PATH.exists():
        pytest.fail(
            f"Missing deterministic seed file: {CAMBIUM_BASELINE_SEED_SQL_PATH}"
        )
    return CAMBIUM_BASELINE_SEED_SQL_PATH


@pytest.fixture(scope="session")
def cambium_proxy_baseline_seed(cambium_proxy_baseline_seed_path: Path) -> str:
    seed_sql = cambium_proxy_baseline_seed_path.read_text(encoding="utf-8")
    _assert_cambium_baseline_seed_contract(seed_sql)
    return seed_sql


@pytest.fixture(scope="session")
def radius_policy_precondition(
    radius_client: Client,
    skip_if_no_radius,
    authorization_matrix_seed: str,
):
    try:
        probe_reply = send_access_request(
            radius_client,
            username=PROBE_USER,
            password=PROBE_PASS,
            nas_ip=PROBE_NAS_IP,
        )
    except Timeout:
        pytest.skip(
            f"FreeRADIUS unreachable or timed out at {RADIUS_HOST}:{RADIUS_PORT}"
        )

    try:
        validate_policy_probe_reply(
            probe_reply,
            expected_marker=PROBE_MARKER,
            expected_cir_attrs=PROBE_CIR_ATTRS,
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    return {
        "probe_user": PROBE_USER,
        "probe_nas_ip": PROBE_NAS_IP,
        "probe_marker": PROBE_MARKER,
        "probe_cir_attrs": PROBE_CIR_ATTRS,
    }


@pytest.fixture(scope="session")
def radius_cambium_baseline_precondition(
    radius_client: Client,
    skip_if_no_radius,
    cambium_proxy_baseline_seed: str,
):
    del cambium_proxy_baseline_seed  # contract validation side-effect

    try:
        probe_reply = send_access_request(
            radius_client,
            username=BASELINE_PROBE_USER,
            password=BASELINE_PROBE_PASS,
            nas_ip=BASELINE_PROBE_NAS_IP,
            calling_station_id=BASELINE_PROBE_CALLING_STATION_ID,
        )
    except Timeout:
        pytest.skip(
            f"FreeRADIUS unreachable or timed out at {RADIUS_HOST}:{RADIUS_PORT}"
        )

    if probe_reply.code != packet.AccessAccept:
        pytest.fail(
            "cambium baseline seed missing or nas_based_authorization disabled "
            f"(probe expected Access-Accept, got code={probe_reply.code})"
        )

    if not reply_contains_marker(probe_reply, BASELINE_PROBE_MARKER):
        pytest.fail("cambium baseline seed missing or marker not hydrated")

    attrs = parse_reply_attributes(probe_reply)
    userlevel_values = attrs.get("Cambium-Canopy-UserLevel", []) + attrs.get(
        "Motorola-Cambium-Canopy-UserLevel", []
    )
    if BASELINE_PROBE_USERLEVEL not in userlevel_values:
        pytest.fail(
            "cambium baseline probe expected userlevel not found "
            f"(expected={BASELINE_PROBE_USERLEVEL}, got={userlevel_values})"
        )

    return {
        "probe_user": BASELINE_PROBE_USER,
        "probe_nas_ip": BASELINE_PROBE_NAS_IP,
        "probe_calling_station_id": BASELINE_PROBE_CALLING_STATION_ID,
        "probe_marker": BASELINE_PROBE_MARKER,
        "probe_userlevel": BASELINE_PROBE_USERLEVEL,
    }
