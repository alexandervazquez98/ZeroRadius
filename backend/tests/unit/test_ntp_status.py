"""
NTP status via SNTP against NTP_SERVER (#122).

A fake NTP server on 127.0.0.1 answers SNTP requests so the offset,
stratum, validation and alert rules are tested without network access.
"""

import socket
import struct
import threading
import time

import pytest

from app.services import ntp_status

NTP_EPOCH_DELTA = 2208988800  # seconds between 1900-01-01 and 1970-01-01


def _to_ntp(ts: float) -> bytes:
    secs = int(ts) + NTP_EPOCH_DELTA
    frac = int((ts % 1) * 2**32)
    return struct.pack("!II", secs, frac)


class FakeNtpServer:
    """Answers each request once. skew: seconds added to the server clock."""

    def __init__(self, skew=0.0, stratum=2, echo_originate=True, mode=4):
        self.skew = skew
        self.stratum = stratum
        self.echo_originate = echo_originate
        self.mode = mode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(3)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            data, addr = self.sock.recvfrom(512)
        except OSError:
            return
        now = time.time() + self.skew
        client_transmit = data[40:48]
        originate = client_transmit if self.echo_originate else b"\x00" * 8
        first = (0 << 6) | (4 << 3) | self.mode
        packet = struct.pack("!BBbb", first, self.stratum, 6, -20)
        packet += b"\x00" * 8  # root delay + root dispersion
        packet += b"GPS\x00"  # reference id
        packet += _to_ntp(now)  # reference timestamp
        packet += originate
        packet += _to_ntp(now)  # receive
        packet += _to_ntp(now)  # transmit
        self.sock.sendto(packet, addr)

    def close(self):
        self.sock.close()


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    ntp_status.clear_cache()
    monkeypatch.delenv("NTP_SERVER", raising=False)
    yield
    ntp_status.clear_cache()


def _use(monkeypatch, server):
    monkeypatch.setenv("NTP_SERVER", f"127.0.0.1:{server.port}")


def test_not_configured_is_not_an_alarm():
    status = ntp_status.get_status()
    assert status.configured is False
    assert status.synchronized is False
    assert status.alert is False


def test_synchronized_when_server_answers_with_small_offset(monkeypatch):
    server = FakeNtpServer(skew=0.0, stratum=2)
    _use(monkeypatch, server)
    status = ntp_status.get_status()
    server.close()

    assert status.configured is True
    assert status.synchronized is True
    assert status.alert is False
    assert status.offset_ms < 100
    assert status.stratum == 2
    assert status.reference_server == f"127.0.0.1:{server.port}"
    assert status.last_sync is not None


def test_large_offset_raises_alert(monkeypatch):
    server = FakeNtpServer(skew=2.0)
    _use(monkeypatch, server)
    status = ntp_status.get_status()
    server.close()

    assert status.synchronized is True
    assert 1900 < status.offset_ms < 2100
    assert status.alert is True


def test_unreachable_server_raises_alert(monkeypatch):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))  # bound but never answers
    monkeypatch.setenv("NTP_SERVER", f"127.0.0.1:{sock.getsockname()[1]}")
    monkeypatch.setattr(ntp_status, "SNTP_TIMEOUT", 0.3)
    status = ntp_status.get_status()
    sock.close()

    assert status.configured is True
    assert status.synchronized is False
    assert status.alert is True


@pytest.mark.parametrize("kwargs", [
    {"stratum": 0},  # kiss-o'-death / unsynchronized server
    {"echo_originate": False},  # not an answer to our request
    {"mode": 3},  # not a server reply
])
def test_invalid_reply_is_not_synchronized(monkeypatch, kwargs):
    server = FakeNtpServer(**kwargs)
    _use(monkeypatch, server)
    monkeypatch.setattr(ntp_status, "SNTP_TIMEOUT", 0.5)
    status = ntp_status.get_status()
    server.close()

    assert status.synchronized is False
    assert status.alert is True


def test_result_is_cached(monkeypatch):
    server = FakeNtpServer()  # answers only once
    _use(monkeypatch, server)
    first = ntp_status.get_status()
    second = ntp_status.get_status()
    server.close()

    assert first.synchronized is True
    assert second == first
