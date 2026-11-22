"""Regression test for issue #102: production must not run ``freeradius -X``.

``docker-compose.yml`` and the radius ``Dockerfile`` hardcoded
``freeradius -X`` and the entrypoint ran ``exec "$@"``, so ``RADIUS_DEBUG``
had no effect. In ``-X`` mode FreeRADIUS prints every decoded request,
including the decrypted ``User-Password`` of PAP logins, to the container
log.

Contract enforced here:

1. Neither the image default nor the production compose file starts
   FreeRADIUS in debug mode.
2. The entrypoint switches to ``freeradius -X`` only when
   ``RADIUS_DEBUG=yes``; otherwise it runs the default command unchanged.
3. A command that is not ``freeradius`` (e.g. a shell for troubleshooting)
   is passed through untouched regardless of ``RADIUS_DEBUG``.
4. The test stack keeps running in debug mode (previous behavior).

The entrypoint check runs the real command-selection block of
``radius/docker-entrypoint.sh`` with ``exec`` replaced by ``printf`` so the
resulting argv can be asserted without Docker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/unit -> repo root
ENTRYPOINT = REPO_ROOT / "radius" / "docker-entrypoint.sh"
DOCKERFILE = REPO_ROOT / "radius" / "Dockerfile"
COMMAND_MARKER = "# --- Start FreeRADIUS ---"


def _service(compose_file: str, name: str) -> dict:
    data = yaml.safe_load((REPO_ROOT / compose_file).read_text())
    return data["services"][name]


def _dockerfile_cmd() -> str:
    cmd_lines = [
        line for line in DOCKERFILE.read_text().splitlines() if line.startswith("CMD ")
    ]
    assert len(cmd_lines) == 1, f"expected exactly one CMD in Dockerfile, got {cmd_lines}"
    return cmd_lines[0]


def _run_command_block(args: list[str], radius_debug: str | None) -> list[str]:
    """Run the entrypoint's command-selection block and return the final argv."""
    content = ENTRYPOINT.read_text()
    assert COMMAND_MARKER in content, (
        f"docker-entrypoint.sh must keep the '{COMMAND_MARKER}' block that "
        f"selects the FreeRADIUS command (issue #102)"
    )
    block = content.split(COMMAND_MARKER, 1)[1]
    assert 'exec "$@"' in block, "command block must end by exec'ing the selected argv"
    block = block.replace('exec "$@"', "printf '%s\\n' \"$@\"")

    env = {k: v for k, v in os.environ.items() if k != "RADIUS_DEBUG"}
    if radius_debug is not None:
        env["RADIUS_DEBUG"] = radius_debug

    result = subprocess.run(
        ["sh", "-c", block, "docker-entrypoint.sh", *args],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    return result.stdout.splitlines()


pytestmark = pytest.mark.skipif(shutil.which("sh") is None, reason="needs POSIX sh")


class TestDefaultsAreNotDebug:
    def test_regression_dockerfile_cmd_is_not_debug(self):
        cmd = _dockerfile_cmd()
        assert '"-X"' not in cmd, f"image default must not be debug mode: {cmd}"
        assert '"-f"' in cmd, f"FreeRADIUS must stay in the foreground in Docker: {cmd}"

    def test_regression_production_compose_does_not_force_debug(self):
        radius = _service("docker-compose.yml", "radius")
        command = radius.get("command") or []
        assert "-X" not in command, (
            f"docker-compose.yml must not hardcode freeradius -X (issue #102): {command}"
        )
        assert radius["environment"]["RADIUS_DEBUG"] == "${RADIUS_DEBUG:-no}"


class TestEntrypointHonorsRadiusDebug:
    DEFAULT_ARGS = ["freeradius", "-f", "-l", "stdout"]

    @pytest.mark.parametrize("value", [None, "no", ""])
    def test_regression_debug_off_keeps_default_command(self, value):
        assert _run_command_block(self.DEFAULT_ARGS, value) == self.DEFAULT_ARGS

    def test_debug_yes_switches_to_debug_mode(self):
        assert _run_command_block(self.DEFAULT_ARGS, "yes") == ["freeradius", "-X"]

    def test_non_freeradius_command_passes_through(self):
        assert _run_command_block(["sh", "-c", "true"], "yes") == ["sh", "-c", "true"]


_ACCESS_BLOCK = [
    b"(0) Received Access-Request Id 1 from 10.0.0.1:1 to 10.0.0.2:1812 length 20\n",
    b"(0)   User-Name = \"alice\"\n",
    b"(0) Sent Access-Accept Id 1 from 10.0.0.2:1812 to 10.0.0.1:1 length 0\n",
]


class _FakeContainer:
    def __init__(self, env: list[str], log_lines: list[bytes] | None = None):
        self.attrs = {"Config": {"Env": env}}
        self._log_lines = log_lines or []

    def logs(self, **_kwargs):
        return iter(self._log_lines)


def _stream_messages(
    monkeypatch, container: _FakeContainer, count: int
) -> tuple[list[dict], int | None]:
    """Open the log stream against a fake radius container.

    Returns the first ``count`` messages and, if the server then closes the
    socket with an explicit code, that code (``None`` otherwise).
    """
    import json
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import system

    async def _fake_auth(_token):
        return SimpleNamespace(username="admin")

    fake_client = SimpleNamespace(
        containers=SimpleNamespace(get=lambda _name: container)
    )
    monkeypatch.setattr(system, "_authenticate_ws", _fake_auth)
    monkeypatch.setattr(system.docker, "from_env", lambda: fake_client)

    app = FastAPI()
    app.include_router(system.router)
    from starlette.websockets import WebSocketDisconnect

    with TestClient(app).websocket_connect("/system/logs/stream") as ws:
        ws.send_text("token")
        messages = [json.loads(ws.receive_text()) for _ in range(count)]
        close_code = None
        if count == 2 and "error" in messages[-1]:
            try:
                ws.receive_text()
            except WebSocketDisconnect as exc:
                close_code = exc.code
    return messages, close_code


class TestLogViewerRequiresDebug:
    """The Live Log Viewer parses -X output; without debug mode it must say
    so instead of streaming nothing (issue #102, option: debug-only viewer)."""

    @pytest.mark.parametrize("env", [[], ["RADIUS_DEBUG=no"], ["RADIUS_DEBUG="]])
    def test_regression_stream_refuses_without_debug(self, monkeypatch, env):
        container = _FakeContainer(env, _ACCESS_BLOCK)
        messages, close_code = _stream_messages(monkeypatch, container, 2)
        assert messages[0] == {"status": "connected"}
        assert "RADIUS_DEBUG=yes" in messages[1].get("error", ""), messages[1]
        assert close_code == 4006

    def test_stream_still_emits_events_in_debug_mode(self, monkeypatch):
        container = _FakeContainer(["RADIUS_DEBUG=yes"], _ACCESS_BLOCK)
        messages, _ = _stream_messages(monkeypatch, container, 2)
        assert messages[0] == {"status": "connected"}
        assert messages[1]["verdict"] == "Accept"
        assert messages[1]["lines"][1] == '(0)   User-Name = "alice"'


class TestTestStackStaysInDebug:
    def test_test_stack_still_runs_debug(self):
        radius = _service("docker-compose.test.yml", "test-radius")
        command = radius.get("command") or []
        assert "-X" in command or radius["environment"].get("RADIUS_DEBUG") == "yes"
