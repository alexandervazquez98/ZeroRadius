"""Baseline regression coverage for real Cambium AP proxy behavior.

These tests intentionally lock the CURRENT behavior before refactoring
nas_based_authorization attribute hydration.
"""

import pytest
from pyrad import packet
from pyrad.client import Timeout

from conftest import parse_reply_attributes, reply_contains_marker, send_access_request

pytestmark = pytest.mark.radius


def _userlevel_values(attrs: dict[str, list[str]]) -> list[str]:
    return attrs.get("Cambium-Canopy-UserLevel", []) + attrs.get(
        "Motorola-Cambium-Canopy-UserLevel", []
    )


def _usermode_values(attrs: dict[str, list[str]]) -> list[str]:
    return attrs.get("Cambium-Canopy-UserMode", []) + attrs.get(
        "Motorola-Cambium-Canopy-UserMode", []
    )


@pytest.mark.parametrize(
    "calling_station_id, expected_marker, expected_userlevel",
    [
        # AP directo (sin SM): hoy cae en regla NAS-IP y devuelve grupo AP.
        (None, "BASELINE-AP-DIRECT", "3"),
        # SM vía proxy: misma NAS-IP, pero la regla por Calling-Station-Id gana.
        ("AA-BB-CC-DD-EE-FF", "BASELINE-SM-LECTOR-SINGLE", "1"),
    ],
)
def test_baseline_ap_direct_vs_sm_proxy_priority(
    radius_client,
    radius_cambium_baseline_precondition,
    calling_station_id: str | None,
    expected_marker: str,
    expected_userlevel: str,
):
    """Baseline real: SQL-Group se resuelve bien entre AP directo y SM proxied."""
    del radius_cambium_baseline_precondition

    try:
        reply = send_access_request(
            radius_client,
            username="baseline_sm_lector_single",
            password="testpassword",
            nas_ip="192.168.88.1",
            calling_station_id=calling_station_id,
        )
    except Timeout:
        pytest.skip("FreeRADIUS timed out")

    assert reply.code == packet.AccessAccept
    assert reply_contains_marker(reply, expected_marker)

    attrs = parse_reply_attributes(reply)
    assert expected_userlevel in _userlevel_values(attrs)


def test_baseline_sm_lector_single_reply_attribute(
    radius_client,
    radius_cambium_baseline_precondition,
):
    """Caso real validado: el SM lector recibe Cambium-Canopy-UserLevel := 1."""
    del radius_cambium_baseline_precondition

    reply = send_access_request(
        radius_client,
        username="baseline_sm_lector_single",
        password="testpassword",
        nas_ip="192.168.88.1",
        calling_station_id="AA-BB-CC-DD-EE-FF",
    )

    assert reply.code == packet.AccessAccept
    assert reply_contains_marker(reply, "BASELINE-SM-LECTOR-SINGLE")
    attrs = parse_reply_attributes(reply)
    assert "1" in _userlevel_values(attrs)


def test_baseline_sm_lector_dual_reply_exposes_current_hydration_gap(
    radius_client,
    radius_cambium_baseline_precondition,
):
    """Gap documentado: cuando el grupo tiene 2 reply attrs, hoy UserMode NO sale."""
    del radius_cambium_baseline_precondition

    reply = send_access_request(
        radius_client,
        username="baseline_sm_lector_dual",
        password="testpassword",
        nas_ip="192.168.88.1",
        calling_station_id="00:11:22:33:44:55",
    )

    assert reply.code == packet.AccessAccept
    assert reply_contains_marker(reply, "BASELINE-SM-LECTOR-DUAL")

    attrs = parse_reply_attributes(reply)
    # Baseline esperado actual (NO cambiar hasta el refactor):
    # - UserLevel sí aparece
    # - UserMode todavía no se hidrata automáticamente
    assert "1" in _userlevel_values(attrs)
    assert _usermode_values(attrs) == []


def test_baseline_group_with_check_and_reply(
    radius_client,
    radius_cambium_baseline_precondition,
):
    """Baseline: grupo con radgroupcheck + radgroupreply sigue devolviendo Access-Accept."""
    del radius_cambium_baseline_precondition

    reply = send_access_request(
        radius_client,
        username="baseline_sm_check_reply",
        password="testpassword",
        nas_ip="192.168.88.1",
        calling_station_id="DE-AD-DE-AD-BE-EF",
        nas_port=0,
    )

    assert reply.code == packet.AccessAccept
    assert reply_contains_marker(reply, "BASELINE-SM-CHECK-REPLY")
    attrs = parse_reply_attributes(reply)
    assert "1" in _userlevel_values(attrs)


def test_baseline_zero_trust_reject_without_match(
    radius_client,
    radius_cambium_baseline_precondition,
):
    """Baseline zero-trust: credencial válida sin match de política => Access-Reject."""
    del radius_cambium_baseline_precondition

    reply = send_access_request(
        radius_client,
        username="baseline_zero_trust",
        password="testpassword",
        nas_ip="192.168.88.1",
    )

    assert reply.code == packet.AccessReject

    attrs = parse_reply_attributes(reply)
    for marker in {
        "BASELINE-AP-DIRECT",
        "BASELINE-SM-LECTOR-SINGLE",
        "BASELINE-SM-LECTOR-DUAL",
        "BASELINE-SM-CHECK-REPLY",
    }:
        assert not reply_contains_marker(reply, marker)

    assert _userlevel_values(attrs) == []
    assert _usermode_values(attrs) == []
