"""
Tests for rsyslog/syslog-forwarder.py parsing.

Run: python -m pytest rsyslog/tests -q   (needs `requests` installed)

Regression: device_ip was taken from words inside the message text, so a
normal RFC 3164 line stored the time ("17:52:31") as the device IP and
GET /syslog/nas-status could never match a registered NAS.
"""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "syslog-forwarder.py"
_spec = importlib.util.spec_from_file_location("syslog_forwarder", _PATH)
fwd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fwd)

SRC = "192.168.1.10"


def test_rfc3164_uses_udp_source_ip_not_message_words():
    e = fwd.parse_syslog(
        "<134>Nov 23 17:52:31 dev zr-healthcheck: pipeline test", SRC
    )
    assert e["device_ip"] == SRC
    assert e["program"] == "zr-healthcheck"
    assert e["message"] == "pipeline test"
    assert (e["facility"], e["severity"]) == (16, 6)


def test_rfc3164_tag_with_pid():
    e = fwd.parse_syslog("<38>Nov  3 07:01:02 host sshd[812]: Accepted publickey", SRC)
    assert e["program"] == "sshd"
    assert e["message"] == "Accepted publickey"
    assert (e["facility"], e["severity"]) == (4, 6)


def test_cisco_ios_sequence_and_millisecond_timestamp():
    e = fwd.parse_syslog(
        "<189>45: *Nov 23 17:52:31.123: %SYS-5-CONFIG_I: Configured from console by zr-test on vty0",
        SRC,
    )
    assert e["device_ip"] == SRC
    assert e["program"] == "%SYS-5-CONFIG_I"
    assert e["message"] == "Configured from console by zr-test on vty0"
    assert (e["facility"], e["severity"]) == (23, 5)


def test_cisco_ios_with_hostname_and_timezone():
    e = fwd.parse_syslog(
        "<187>112: sw-oficina: Nov 23 2026 17:52:31.456 UTC: %LINK-3-UPDOWN: Interface Gi1/0/3, changed state to down",
        SRC,
    )
    assert e["program"] == "%LINK-3-UPDOWN"
    assert e["message"] == "Interface Gi1/0/3, changed state to down"
    assert e["severity"] == 3


def test_mikrotik_topics_become_program():
    e = fwd.parse_syslog(
        "<134>system,info,account user admin logged in from 192.168.1.99 via winbox", SRC
    )
    assert e["device_ip"] == SRC
    assert e["program"] == "system,info,account"
    assert e["message"] == "user admin logged in from 192.168.1.99 via winbox"


def test_rfc5424_without_structured_data():
    e = fwd.parse_syslog(
        "<165>1 2026-11-23T17:52:31.003Z moxa-lab webd 1234 ID47 - Login failed for admin",
        SRC,
    )
    assert e["device_ip"] == SRC
    assert e["program"] == "webd"
    assert e["message"] == "Login failed for admin"
    assert (e["facility"], e["severity"]) == (20, 5)


def test_rfc5424_with_structured_data_and_nil_app():
    e = fwd.parse_syslog(
        '<14>1 2026-11-23T17:52:31Z host - - - [origin ip="10.0.0.1"][meta x="a\\]b"] link up',
        SRC,
    )
    assert e["program"] is None
    assert e["message"] == "link up"


def test_message_without_header_keeps_text():
    e = fwd.parse_syslog("<30>just a message", SRC)
    assert e["device_ip"] == SRC
    assert e["program"] is None
    assert e["message"] == "just a message"


def test_message_without_priority_falls_back():
    e = fwd.parse_syslog("no priority here", SRC)
    assert e["device_ip"] == SRC
    assert (e["facility"], e["severity"]) == (1, 6)
    assert e["message"] == "no priority here"


def test_program_truncated_to_column_size():
    e = fwd.parse_syslog("<134>Nov 23 17:52:31 h " + "x" * 80 + ": hi", SRC)
    assert len(e["program"]) == 64
    assert e["message"] == "hi"


def test_received_at_is_utc_iso():
    e = fwd.parse_syslog("<134>Nov 23 17:52:31 h app: hi", SRC)
    assert e["received_at"].endswith("Z")


def test_handle_client_records_source_address(monkeypatch):
    monkeypatch.setattr(fwd, "flush_buffer", lambda: None)
    fwd.message_buffer.clear()
    fwd.handle_client(b"<134>Nov 23 17:52:31 dev app: hello", ("192.168.1.190", 40000))
    assert fwd.message_buffer[-1]["device_ip"] == "192.168.1.190"
    fwd.message_buffer.clear()


@pytest.mark.parametrize("raw", ["", "   "])
def test_handle_client_ignores_empty(monkeypatch, raw):
    monkeypatch.setattr(fwd, "flush_buffer", lambda: None)
    fwd.message_buffer.clear()
    fwd.handle_client(raw.encode(), ("192.168.1.190", 40000))
    assert fwd.message_buffer == []


# RouterOS remote logging (bsd-syslog=no) sends no <PRI>: "system,info log rule added by admin".
@pytest.mark.parametrize(
    "raw, program, severity",
    [
        ("system,info log rule added by admin", "system,info", 6),
        ("system,error,critical login failure for user admin via ssh", "system,error,critical", 2),
        ("interface,warning ether2 link down", "interface,warning", 4),
        ("dhcp,debug,packet dhcp1 received discover", "dhcp,debug,packet", 7),
    ],
)
def test_mikrotik_without_priority_uses_topics(raw, program, severity):
    e = fwd.parse_syslog(raw, SRC)
    assert e["device_ip"] == SRC
    assert e["program"] == program
    assert e["message"] == raw.split(" ", 1)[1]
    assert e["severity"] == severity


def test_comma_words_without_severity_topic_stay_unparsed():
    e = fwd.parse_syslog("foo,bar baz qux", SRC)
    assert e["program"] is None
    assert e["message"] == "foo,bar baz qux"
    assert e["severity"] == 6
