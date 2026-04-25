import pytest
from pyrad import packet

from conftest import (
    RadiusScenario,
    parse_reply_attributes,
    reply_contains_marker,
    validate_policy_probe_reply,
)


class _FakeReply:
    def __init__(self, code: int, attrs: dict[str, list[str]]):
        self.code = code
        self._attrs = attrs

    def keys(self):
        return self._attrs.keys()

    def __getitem__(self, key):
        return self._attrs[key]


def test_regression_radius_scenario_contract_stores_expected_fields():
    scenario = RadiusScenario(
        username="segment_admin_a",
        password="testpassword",
        nas_ip="192.168.10.50",
        expected_code=packet.AccessAccept,
        expected_marker="MATRIX-EXACT-A",
        expected_cir_attrs={"Cambium-Canopy-HPDLCIR": "5000"},
    )

    assert scenario.username == "segment_admin_a"
    assert scenario.expected_marker == "MATRIX-EXACT-A"
    assert scenario.expected_cir_attrs["Cambium-Canopy-HPDLCIR"] == "5000"


def test_regression_reply_parser_and_marker_detection_work_with_reply_payload():
    reply = _FakeReply(
        packet.AccessAccept,
        {
            "Reply-Message": ["MATRIX-EXACT-A"],
            "Cambium-Canopy-HPDLCIR": ["5000"],
        },
    )

    parsed = parse_reply_attributes(reply)
    assert parsed["Reply-Message"] == ["MATRIX-EXACT-A"]
    assert reply_contains_marker(reply, "MATRIX-EXACT-A") is True
    assert reply_contains_marker(reply, "MATRIX-RANGE-A") is False


def test_regression_reply_parser_decodes_vendor_tuple_cir_values():
    reply = _FakeReply(
        packet.AccessAccept,
        {
            "Reply-Message": ["MATRIX-EXACT-A"],
            (161, 22): [b"\x00\x00\x13\x88"],
            (161, 23): [b"\x00\x00\x07\xd0"],
        },
    )

    parsed = parse_reply_attributes(reply)
    assert parsed["Cambium-Canopy-HPDLCIR"] == ["5000"]
    assert parsed["Cambium-Canopy-HPULCIR"] == ["2000"]


def test_regression_policy_probe_validation_fails_loudly_when_marker_missing():
    reply = _FakeReply(
        packet.AccessAccept,
        {
            "Reply-Message": ["UNRELATED-MARKER"],
            "Cambium-Canopy-HPDLCIR": ["5000"],
            "Cambium-Canopy-HPULCIR": ["2000"],
        },
    )

    with pytest.raises(AssertionError) as exc:
        validate_policy_probe_reply(
            reply,
            expected_marker="MATRIX-EXACT-A",
            expected_cir_attrs={
                "Cambium-Canopy-HPDLCIR": "5000",
                "Cambium-Canopy-HPULCIR": "2000",
            },
        )

    assert "nas_based_authorization disabled or seed missing" in str(exc.value)
