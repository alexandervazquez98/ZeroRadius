"""
Tests for rsyslog/syslog-forwarder.py parsing.

Run: python -m pytest rsyslog/tests -q   (needs `requests` installed)

Regression: device_ip was taken from words inside the message text, so a
normal RFC 3164 line stored the time ("17:52:31") as the device IP and
GET /syslog/nas-status could never match a registered NAS.
"""

import importlib.util
import socket
import threading
import time
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


def _forwarder(**kw):
    sent = []
    kw.setdefault("send", lambda batch: sent.append(list(batch)) or True)
    kw.setdefault("batch_size", 50)
    kw.setdefault("batch_timeout", 60)
    return fwd.Forwarder(**kw), sent


def _ev(n, severity=6):
    return {"message": f"m{n}", "severity": severity}


def test_handle_client_records_source_address(monkeypatch):
    f, _ = _forwarder()
    monkeypatch.setattr(fwd, "FORWARDER", f)
    fwd.handle_client(b"<134>Nov 23 17:52:31 dev app: hello", ("192.168.1.190", 40000))
    assert f.pending()[-1]["device_ip"] == "192.168.1.190"


@pytest.mark.parametrize("raw", ["", "   "])
def test_handle_client_ignores_empty(monkeypatch, raw):
    f, _ = _forwarder()
    monkeypatch.setattr(fwd, "FORWARDER", f)
    fwd.handle_client(raw.encode(), ("192.168.1.190", 40000))
    assert f.pending() == []


def test_handle_client_never_sends_on_the_receive_path(monkeypatch):
    # Regression: every datagram triggered its own POST on the UDP thread.
    f, sent = _forwarder(batch_size=1)
    monkeypatch.setattr(fwd, "FORWARDER", f)
    for _ in range(3):
        fwd.handle_client(b"<134>Nov 23 17:52:31 dev app: hello", ("10.0.0.1", 1))
    assert sent == []
    assert len(f.pending()) == 3


def test_full_batch_is_returned_without_waiting_for_timeout():
    f, _ = _forwarder(batch_size=3, batch_timeout=60)
    for n in range(3):
        f.submit(_ev(n))
    start = time.monotonic()
    assert [e["message"] for e in f.next_batch()] == ["m0", "m1", "m2"]
    assert time.monotonic() - start < 1


def test_partial_batch_is_returned_after_timeout():
    f, _ = _forwarder(batch_size=100, batch_timeout=0.1)
    f.submit(_ev(0))
    f.submit(_ev(1))
    start = time.monotonic()
    assert len(f.next_batch()) == 2
    assert time.monotonic() - start >= 0.09


def test_batch_never_exceeds_batch_size():
    f, _ = _forwarder(batch_size=2)
    for n in range(5):
        f.submit(_ev(n))
    assert [e["message"] for e in f.next_batch()] == ["m0", "m1"]
    assert [e["message"] for e in f.next_batch()] == ["m2", "m3"]
    assert [e["message"] for e in f.pending()] == ["m4"]


def test_buffer_is_bounded_and_drops_oldest():
    f, _ = _forwarder(max_buffer=3)
    for n in range(5):
        f.submit(_ev(n))
    assert [e["message"] for e in f.pending()] == ["m2", "m3", "m4"]
    assert f.stats()["dropped"] == 2


def test_failed_delivery_requeues_batch_in_order_ahead_of_new_messages():
    f, _ = _forwarder(send=lambda batch: False, batch_size=2)
    f.submit(_ev(0))
    f.submit(_ev(1))
    batch = f.next_batch()
    f.submit(_ev(2))
    assert f.deliver(batch) is False
    assert [e["message"] for e in f.pending()] == ["m0", "m1", "m2"]
    assert f.stats()["forwarded"] == 0


def test_failed_delivery_requeue_respects_bound():
    f, _ = _forwarder(send=lambda batch: False, batch_size=2, max_buffer=3)
    f.submit(_ev(0))
    f.submit(_ev(1))
    batch = f.next_batch()
    f.submit(_ev(2))
    f.submit(_ev(3))
    f.deliver(batch)
    assert [e["message"] for e in f.pending()] == ["m1", "m2", "m3"]
    assert f.stats()["dropped"] == 1


def test_send_exception_counts_as_failed_delivery():
    def boom(batch):
        raise ConnectionError("backend down")

    f, _ = _forwarder(send=boom, batch_size=1)
    f.submit(_ev(0))
    assert f.deliver(f.next_batch()) is False
    assert [e["message"] for e in f.pending()] == ["m0"]
    assert f.stats()["failed_posts"] == 1


def test_successful_delivery_counts_forwarded():
    f, sent = _forwarder(batch_size=2)
    f.submit(_ev(0))
    f.submit(_ev(1))
    assert f.deliver(f.next_batch()) is True
    assert len(sent) == 1 and f.stats()["forwarded"] == 2


def test_min_severity_filters_less_severe_messages():
    f, _ = _forwarder(min_severity=5)
    f.submit(_ev(0, severity=6))  # info: dropped
    f.submit(_ev(1, severity=5))  # notice: kept
    f.submit(_ev(2, severity=3))  # error: kept
    assert [e["message"] for e in f.pending()] == ["m1", "m2"]
    assert f.stats()["filtered"] == 1


def test_no_min_severity_keeps_everything():
    f, _ = _forwarder()
    f.submit(_ev(0, severity=7))
    assert len(f.pending()) == 1


@pytest.mark.parametrize(
    "raw, expected",
    [("", None), ("notice", 5), ("INFO", 6), ("4", 4), ("warning", 4), ("bogus", None), ("9", None)],
)
def test_parse_min_severity(raw, expected):
    assert fwd.parse_min_severity(raw) == expected


def test_run_loop_sends_one_post_per_batch():
    f, sent = _forwarder(batch_size=3, batch_timeout=60)
    stop = threading.Event()
    worker = threading.Thread(target=f.run, args=(stop,), daemon=True)
    worker.start()
    for n in range(3):
        f.submit(_ev(n))
    deadline = time.monotonic() + 2
    while not sent and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    f.wake()
    worker.join(2)
    assert [len(b) for b in sent] == [3]
    assert not worker.is_alive()


def test_stop_flushes_pending_messages():
    f, sent = _forwarder(batch_size=100, batch_timeout=60)
    stop = threading.Event()
    worker = threading.Thread(target=f.run, args=(stop,), daemon=True)
    worker.start()
    f.submit(_ev(0))
    stop.set()
    f.wake()
    worker.join(2)
    assert [len(b) for b in sent] == [1]


class _Resp:
    def __init__(self, status):
        self.status_code = status
        self.text = "x"


@pytest.mark.parametrize("status, ok", [(201, True), (200, True), (500, False), (401, False)])
def test_post_to_backend_reports_status(monkeypatch, status, ok):
    monkeypatch.setattr(fwd.requests, "post", lambda *a, **k: _Resp(status))
    assert fwd.post_to_backend([_ev(0)]) is ok


def test_post_to_backend_propagates_network_errors(monkeypatch):
    def down(*a, **k):
        raise fwd.requests.ConnectionError("refused")

    monkeypatch.setattr(fwd.requests, "post", down)
    with pytest.raises(fwd.requests.ConnectionError):
        fwd.post_to_backend([_ev(0)])


def test_udp_socket_gets_a_larger_receive_buffer():
    sock = fwd.open_udp_socket("127.0.0.1", 0, rcvbuf=1 << 20)
    try:
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF) >= 256 * 1024
    finally:
        sock.close()


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
