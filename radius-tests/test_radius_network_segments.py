"""RADIUS precedence/CIR matrix for deterministic segment authorization."""

import json
import os
from urllib import error as urllib_error
from urllib import request as urllib_request

import pytest
from pyrad import packet
from pyrad.client import Timeout

from conftest import (
    RadiusScenario,
    assert_cir_attributes,
    parse_reply_attributes,
    reply_contains_marker,
    send_access_request,
)

pytestmark = pytest.mark.radius

ALL_MARKERS = {
    "MATRIX-EXACT-A",
    "MATRIX-RANGE-A",
    "MATRIX-BASE-A",
    "MATRIX-FALLBACK-A",
    "MATRIX-EXACT-B",
    "MATRIX-RANGE-B",
    "MATRIX-BASE-B",
    "MATRIX-FALLBACK-B",
}

CIR_ATTR_NAMES = [
    "Cambium-Canopy-HPDLCIR",
    "Cambium-Canopy-HPULCIR",
    "Cambium-Canopy-LPDLCIR",
    "Cambium-Canopy-LPULCIR",
]

MARKER_TO_RESOLUTION_PATH = {
    "MATRIX-EXACT-A": "exact",
    "MATRIX-EXACT-B": "exact",
    "MATRIX-RANGE-A": "range",
    "MATRIX-RANGE-B": "range",
    "MATRIX-BASE-A": "segment",
    "MATRIX-BASE-B": "segment",
    "MATRIX-FALLBACK-A": "category",
    "MATRIX-FALLBACK-B": "category",
}

CIR_PREVIEW_URL = os.getenv("CIR_PREVIEW_URL", "http://127.0.0.1:8000/cir/preview")
CIR_PREVIEW_BEARER_TOKEN = os.getenv("CIR_PREVIEW_BEARER_TOKEN", "").strip()


def _expected_resolution_path_from_marker(marker: str) -> str:
    path = MARKER_TO_RESOLUTION_PATH.get(marker)
    if path is None:
        raise AssertionError(f"Unknown matrix marker for preview parity: {marker}")
    return path


def _fetch_cir_preview(username: str, nas_ip: str) -> dict:
    if not CIR_PREVIEW_BEARER_TOKEN:
        pytest.skip(
            "Set CIR_PREVIEW_BEARER_TOKEN to enable backend preview parity assertions"
        )

    payload_bytes = json.dumps({"username": username, "nas_ip": nas_ip}).encode(
        "utf-8"
    )
    req = urllib_request.Request(
        CIR_PREVIEW_URL,
        data=payload_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CIR_PREVIEW_BEARER_TOKEN}",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                raise AssertionError(
                    f"Preview endpoint returned unexpected status={response.status}"
                )
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.URLError as exc:
        pytest.skip(f"CIR preview endpoint unreachable at {CIR_PREVIEW_URL}: {exc}")


def _assert_winner_marker(reply, expected_marker: str) -> None:
    assert reply_contains_marker(reply, expected_marker), (
        f"Expected winner marker '{expected_marker}' in reply attributes"
    )
    for other_marker in sorted(ALL_MARKERS - {expected_marker}):
        assert not reply_contains_marker(reply, other_marker), (
            f"Marker '{other_marker}' should not appear when '{expected_marker}' wins"
        )


@pytest.mark.parametrize(
    "scenario",
    [
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.50",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-EXACT-A",
            expected_cir_attrs={
                "Cambium-Canopy-HPDLCIR": "5000",
                "Cambium-Canopy-HPULCIR": "2000",
            },
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.60",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-RANGE-A",
            expected_cir_attrs={
                "Cambium-Canopy-HPDLCIR": "4500",
                "Cambium-Canopy-HPULCIR": "1800",
            },
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.100",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-BASE-A",
            expected_cir_attrs=None,
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="10.0.0.50",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-FALLBACK-A",
            expected_cir_attrs=None,
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="172.16.50.10",
            expected_code=packet.AccessReject,
            expected_marker=None,
            expected_cir_attrs=None,
        ),
    ],
)
def test_regression_authorization_precedence_matrix(
    scenario: RadiusScenario,
    radius_client,
    radius_policy_precondition,
):
    try:
        reply = send_access_request(
            radius_client,
            username=scenario.username,
            password=scenario.password,
            nas_ip=scenario.nas_ip,
        )
    except Timeout:
        pytest.skip("FreeRADIUS timed out")

    assert reply.code == scenario.expected_code

    if scenario.expected_code == packet.AccessReject:
        attrs = parse_reply_attributes(reply)
        for marker in ALL_MARKERS:
            assert not reply_contains_marker(reply, marker)
        for cir_attr in CIR_ATTR_NAMES:
            assert cir_attr not in attrs
        return

    assert scenario.expected_marker is not None
    _assert_winner_marker(reply, scenario.expected_marker)

    if scenario.expected_cir_attrs:
        assert_cir_attributes(reply, scenario.expected_cir_attrs)
    else:
        attrs = parse_reply_attributes(reply)
        for cir_attr in CIR_ATTR_NAMES:
            assert cir_attr not in attrs


@pytest.mark.parametrize(
    "scenario",
    [
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.69",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-RANGE-A",
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.70",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-BASE-A",
        ),
        RadiusScenario(
            username="segment_reader_b",
            password="testpassword",
            nas_ip="192.168.10.70",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-RANGE-B",
        ),
        RadiusScenario(
            username="segment_reader_b",
            password="testpassword",
            nas_ip="192.168.10.79",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-RANGE-B",
        ),
        RadiusScenario(
            username="segment_reader_b",
            password="testpassword",
            nas_ip="192.168.10.80",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-BASE-B",
        ),
    ],
)
def test_regression_authorization_range_boundaries(
    scenario: RadiusScenario,
    radius_client,
    radius_policy_precondition,
):
    try:
        reply = send_access_request(
            radius_client,
            username=scenario.username,
            password=scenario.password,
            nas_ip=scenario.nas_ip,
        )
    except Timeout:
        pytest.skip("FreeRADIUS timed out")

    assert reply.code == scenario.expected_code
    assert scenario.expected_marker is not None
    _assert_winner_marker(reply, scenario.expected_marker)


@pytest.mark.parametrize(
    "scenario",
    [
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.50",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-EXACT-A",
            expected_cir_attrs={
                "Cambium-Canopy-HPDLCIR": "5000",
                "Cambium-Canopy-HPULCIR": "2000",
            },
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.60",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-RANGE-A",
            expected_cir_attrs={
                "Cambium-Canopy-HPDLCIR": "4500",
                "Cambium-Canopy-HPULCIR": "1800",
            },
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="192.168.10.100",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-BASE-A",
            expected_cir_attrs=None,
        ),
        RadiusScenario(
            username="segment_admin_a",
            password="testpassword",
            nas_ip="10.0.0.50",
            expected_code=packet.AccessAccept,
            expected_marker="MATRIX-FALLBACK-A",
            expected_cir_attrs=None,
        ),
    ],
)
def test_preview_winner_parity_matches_radius_marker(
    scenario: RadiusScenario,
    radius_client,
    radius_policy_precondition,
):
    reply = send_access_request(
        radius_client,
        username=scenario.username,
        password=scenario.password,
        nas_ip=scenario.nas_ip,
    )
    assert reply.code == packet.AccessAccept
    assert scenario.expected_marker is not None
    _assert_winner_marker(reply, scenario.expected_marker)

    preview_payload = _fetch_cir_preview(scenario.username, scenario.nas_ip)
    assert preview_payload["resolution_path"] == _expected_resolution_path_from_marker(
        scenario.expected_marker
    )


def test_preview_marker_to_resolution_path_mapping_contract():
    assert _expected_resolution_path_from_marker("MATRIX-EXACT-A") == "exact"
    assert _expected_resolution_path_from_marker("MATRIX-RANGE-A") == "range"
    assert _expected_resolution_path_from_marker("MATRIX-BASE-A") == "segment"
    assert _expected_resolution_path_from_marker("MATRIX-FALLBACK-A") == "category"


def test_preview_marker_to_resolution_path_rejects_unknown_marker():
    with pytest.raises(AssertionError, match="Unknown matrix marker"):
        _expected_resolution_path_from_marker("MATRIX-UNKNOWN")
