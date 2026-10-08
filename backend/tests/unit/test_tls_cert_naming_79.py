"""Regression tests for Issue #79 — TLS cert naming mismatch.

Frontend certs were historically named ``nginx.crt`` / ``nginx.key`` in
``frontend/nginx.conf`` while the docker-compose mount and the host-side
``generate_certs.py`` script produced ``server.crt`` / ``server.key``.
This module locks the corrected contract so the breakage cannot regress.

These tests are intentionally pure-stdlib + ``pytest``: no backend
imports, no DB, no fixtures from ``backend/tests/conftest.py``. They
must parse and run on any host that has the dev requirements installed.
"""

from __future__ import annotations

import importlib.util
import io
import os
import re
import socket
import sys
import tokenize
from pathlib import Path
from types import ModuleType

import pytest

# backend/tests/unit/test_tls_cert_naming_79.py  →  parents[3] = repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
NGINX_CONF = REPO_ROOT / "frontend" / "nginx.conf"
GENERATE_CERTS_PY = REPO_ROOT / "generate_certs.py"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _ssl_directive(conf_text: str, directive: str) -> str:
    """Extract the path argument from ``directive /path/to/file;`` in nginx.conf."""
    match = re.search(
        rf"^\s*{re.escape(directive)}\s+(\S+)\s*;", conf_text, flags=re.MULTILINE
    )
    assert match, f"Could not find directive '{directive}' in nginx.conf"
    return match.group(1)


def _code_only_tokens(source: str) -> str:
    """Return ``source`` with comments and string literals blanked out.

    Lets us assert that a legacy constant is absent from *executable code*
    rather than from a docstring that merely references the historical bug.
    """
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    cleaned: list[tokenize.TokenInfo] = []
    for tok in tokens:
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            cleaned.append(
                tokenize.TokenInfo(tok.type, " ", tok.start, tok.end, tok.line)
            )
        else:
            cleaned.append(tok)
    return tokenize.untokenize(cleaned)


def _load_generate_certs_module() -> ModuleType:
    """Import ``generate_certs.py`` as an isolated module without running __main__."""
    spec = importlib.util.spec_from_file_location(
        "_generate_certs_under_test_79", GENERATE_CERTS_PY
    )
    assert spec is not None and spec.loader is not None, (
        f"Cannot build import spec for {GENERATE_CERTS_PY}"
    )
    module = importlib.util.module_from_spec(spec)
    # Register so internal imports (if any are added later) resolve cleanly.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# --------------------------------------------------------------------------- #
# fixture: load each artifact exactly once per test class
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def nginx_conf_text() -> str:
    assert NGINX_CONF.is_file(), f"nginx.conf missing at {NGINX_CONF}"
    return NGINX_CONF.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def generate_certs_source() -> str:
    assert GENERATE_CERTS_PY.is_file(), f"generate_certs.py missing at {GENERATE_CERTS_PY}"
    return GENERATE_CERTS_PY.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def generate_certs_module() -> ModuleType:
    return _load_generate_certs_module()


# --------------------------------------------------------------------------- #
# nginx.conf contract
# --------------------------------------------------------------------------- #


class TestNginxConfCertFilenames:
    """Issue #79, AC #1: nginx.conf must reference server.crt / server.key."""

    def test_ssl_certificate_path_ends_with_server_crt(self, nginx_conf_text: str) -> None:
        cert_path = _ssl_directive(nginx_conf_text, "ssl_certificate")
        assert cert_path.endswith("/server.crt"), (
            f"ssl_certificate should end with /server.crt, got {cert_path!r}"
        )

    def test_ssl_certificate_key_path_ends_with_server_key(self, nginx_conf_text: str) -> None:
        key_path = _ssl_directive(nginx_conf_text, "ssl_certificate_key")
        assert key_path.endswith("/server.key"), (
            f"ssl_certificate_key should end with /server.key, got {key_path!r}"
        )

    def test_no_legacy_nginx_crt_anywhere(self, nginx_conf_text: str) -> None:
        """The old broken filename must be gone from the entire config."""
        assert "nginx.crt" not in nginx_conf_text, (
            "Issue #79 not fully fixed: 'nginx.crt' still appears in "
            "frontend/nginx.conf"
        )

    def test_no_legacy_nginx_key_anywhere(self, nginx_conf_text: str) -> None:
        """The old broken filename must be gone from the entire config."""
        assert "nginx.key" not in nginx_conf_text, (
            "Issue #79 not fully fixed: 'nginx.key' still appears in "
            "frontend/nginx.conf"
        )

    def test_cert_paths_live_under_etc_nginx_certs(self, nginx_conf_text: str) -> None:
        cert_path = _ssl_directive(nginx_conf_text, "ssl_certificate")
        key_path = _ssl_directive(nginx_conf_text, "ssl_certificate_key")
        assert cert_path.startswith("/etc/nginx/certs/"), cert_path
        assert key_path.startswith("/etc/nginx/certs/"), key_path

    def test_directives_use_a_single_path(self, nginx_conf_text: str) -> None:
        """Each directive must declare exactly one path (no include-indirection traps)."""
        for directive in ("ssl_certificate", "ssl_certificate_key"):
            matches = re.findall(
                rf"^\s*{re.escape(directive)}\s+\S+\s*;",
                nginx_conf_text,
                flags=re.MULTILINE,
            )
            assert len(matches) == 1, (
                f"Expected exactly one '{directive}' directive, found {len(matches)}"
            )


# --------------------------------------------------------------------------- #
# generate_certs.py contract
# --------------------------------------------------------------------------- #


class TestGenerateCertsScript:
    """Issue #79, AC #2: generate_certs.py must not hardcode 192.168.1.35."""

    def test_no_hardcoded_legacy_ip(self, generate_certs_source: str) -> None:
        """The literal ``192.168.1.35`` must NOT be reachable from any code path.

        Comments and docstrings are stripped first — those can mention the
        historical bug as documentation without being a real hardcode.
        """
        code_only = _code_only_tokens(generate_certs_source)
        assert "192.168.1.35" not in code_only, (
            "Issue #79 not fully fixed: literal '192.168.1.35' is still "
            "hardcoded as an executable string in generate_certs.py"
        )

    def test_env_var_override_is_honored(self, generate_certs_source: str) -> None:
        """``SERVER_IP`` env var must be read from ``os.environ``."""
        # Scan the original source (strings intact) for any os.environ reference
        # that names ``SERVER_IP``. Accept both dict-style and ``.get()`` access.
        pattern = re.compile(
            r"os\s*\.\s*environ"
            r"(?:\s*\.\s*get\s*\(\s*[\"'](\w+)[\"']"
            r"|\s*\[\s*[\"'](\w+)[\"']\s*\])"
        )
        keys = {a or b for a, b in pattern.findall(generate_certs_source)}
        assert "SERVER_IP" in keys, (
            f"generate_certs.py must read SERVER_IP from os.environ, "
            f"got keys: {sorted(keys)}"
        )

    def test_socket_module_is_imported(self, generate_certs_source: str) -> None:
        assert re.search(
            r"^\s*import\s+socket\s*$", generate_certs_source, flags=re.MULTILINE
        ), "generate_certs.py must import socket for IP detection"

    def test_resolution_helper_is_defined(self, generate_certs_source: str) -> None:
        assert re.search(
            r"^def\s+_resolve_server_ip\b", generate_certs_source, flags=re.MULTILINE
        ), (
            "generate_certs.py must define _resolve_server_ip() for dynamic IP "
            "detection"
        )

    def test_module_level_server_ip_uses_the_helper(
        self, generate_certs_source: str
    ) -> None:
        """The module-level ``SERVER_IP`` must be wired through the resolver."""
        assert re.search(
            r"^SERVER_IP\s*=\s*_resolve_server_ip\s*\(\s*\)",
            generate_certs_source,
            flags=re.MULTILINE,
        ), "Module-level SERVER_IP must be assigned via _resolve_server_ip()"


# --------------------------------------------------------------------------- #
# behavioral checks (real helper, not just source text)
# --------------------------------------------------------------------------- #


class TestResolveServerIpBehavior:
    """Behavior-level checks on the actual helper function."""

    def test_env_override_wins_over_detection(
        self,
        monkeypatch: pytest.MonkeyPatch,
        generate_certs_module: ModuleType,
    ) -> None:
        """When SERVER_IP is set, it must be returned verbatim."""
        monkeypatch.setenv("SERVER_IP", "10.20.30.40")
        assert generate_certs_module._resolve_server_ip() == "10.20.30.40"

    def test_env_override_supports_ipv6_string(
        self,
        monkeypatch: pytest.MonkeyPatch,
        generate_certs_module: ModuleType,
    ) -> None:
        """The env var is a string pass-through; no parsing, no coercion."""
        monkeypatch.setenv("SERVER_IP", "::1")
        assert generate_certs_module._resolve_server_ip() == "::1"

    def test_blank_env_override_is_ignored(
        self,
        monkeypatch: pytest.MonkeyPatch,
        generate_certs_module: ModuleType,
    ) -> None:
        """An empty/whitespace SERVER_IP must NOT win — fall through to detection."""
        monkeypatch.setenv("SERVER_IP", "   ")
        # Fake a successful UDP probe to confirm we did NOT short-circuit on the blank env.
        captured: dict[str, str] = {}

        class FakeSocket:
            def __init__(self, *args, **kwargs):
                pass

            def connect(self, target):
                pass

            def getsockname(self):
                return ("198.51.100.42", 0)

            def close(self):
                pass

        monkeypatch.setattr(socket, "socket", FakeSocket)
        result = generate_certs_module._resolve_server_ip()
        captured["ip"] = result
        assert captured["ip"] == "198.51.100.42", (
            "Blank SERVER_IP env must be treated as unset and fall through to detection"
        )

    def test_detection_returns_probe_ip_when_available(
        self,
        monkeypatch: pytest.MonkeyPatch,
        generate_certs_module: ModuleType,
    ) -> None:
        """With no env override and a working UDP probe, return the detected IP."""
        monkeypatch.delenv("SERVER_IP", raising=False)

        class FakeSocket:
            def __init__(self, *args, **kwargs):
                pass

            def connect(self, target):
                pass

            def getsockname(self):
                return ("203.0.113.7", 0)

            def close(self):
                pass

        monkeypatch.setattr(socket, "socket", FakeSocket)
        assert generate_certs_module._resolve_server_ip() == "203.0.113.7"

    def test_detection_falls_back_safely(
        self,
        monkeypatch: pytest.MonkeyPatch,
        generate_certs_module: ModuleType,
    ) -> None:
        """If every detection path fails, fall back to 127.0.0.1 without raising."""
        monkeypatch.delenv("SERVER_IP", raising=False)

        class FailingSocket:
            def __init__(self, *args, **kwargs):
                pass

            def connect(self, target):
                raise OSError("network unreachable")

            def getsockname(self):
                raise AssertionError("should not be called when connect fails")

            def close(self):
                pass

        monkeypatch.setattr(socket, "socket", FailingSocket)
        monkeypatch.setattr(
            socket,
            "gethostbyname",
            lambda host: (_ for _ in ()).throw(socket.gaierror("no resolution")),
        )
        assert generate_certs_module._resolve_server_ip() == "127.0.0.1"