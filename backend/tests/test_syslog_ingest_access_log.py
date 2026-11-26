"""uvicorn access lines for successful POST /syslog/ingest are dropped (#136).

The forwarder calls ingest continuously; logging each call filled the
container logs. Failures and every other request must still be logged.
"""

import logging

import pytest

from app.main import _SyslogIngestAccessFilter


def _record(method, path, status):
    return logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1,
        '%s - "%s %s HTTP/%s" %d', ("172.18.0.5:41234", method, path, "1.1", status), None,
    )


@pytest.mark.parametrize(
    "method, path, status, logged",
    [
        ("POST", "/syslog/ingest", 201, False),
        ("POST", "/syslog/ingest", 200, False),
        ("POST", "/syslog/ingest", 401, True),
        ("POST", "/syslog/ingest", 500, True),
        ("GET", "/syslog", 200, True),
        ("POST", "/auth/login", 200, True),
    ],
)
def test_filter_drops_only_successful_ingest(method, path, status, logged):
    assert _SyslogIngestAccessFilter().filter(_record(method, path, status)) is logged


def test_filter_keeps_records_with_other_args():
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "plain", None, None)
    assert _SyslogIngestAccessFilter().filter(record) is True


def test_filter_is_installed_on_uvicorn_access_logger():
    filters = logging.getLogger("uvicorn.access").filters
    assert any(isinstance(f, _SyslogIngestAccessFilter) for f in filters)
