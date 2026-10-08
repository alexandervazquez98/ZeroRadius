"""Regression test for issue #78: backend port 8000 must be host-publishable.

The original \`docker-compose.yml\` declared the \`backend\` service with no
\`ports:\` mapping at all, so the FastAPI app was reachable only from
inside the Docker network. The docs (quickstart, deployment, README)
all referenced \`http://localhost:8000/health\` — and that command
silently returned "Connection refused" on a correct deployment.

Fix: \`docker-compose.yml\` now publishes \`127.0.0.1:8000:8000\` so the
operator's shell can reach the API directly (Swagger UI, health checks,
curl examples).

This test enforces the contract: a future refactor that removes the
port mapping (or binds it to \`0.0.0.0\`, exposing the API to the
network) will fail this test.
"""

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/unit -> repo root
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


def _load_backend_service() -> dict:
    """Parse docker-compose.yml and return the backend service definition."""
    with COMPOSE_PATH.open() as fh:
        data = yaml.safe_load(fh)
    services = data.get("services", {})
    assert "backend" in services, (
        "docker-compose.yml is missing the 'backend' service entirely — "
        "this is a more severe regression than issue #78 describes."
    )
    return services["backend"]


def test_backend_service_publishes_port_8000():
    """The backend service must expose 8000 to the host loopback.

    The exact form expected is a port mapping that contains
    \`8000:8000\` and is bound to \`127.0.0.1\`. Other formats (e.g.
    \`"8000"\` for random host port) are not accepted because the
    documented examples assume \`localhost:8000\`.
    """
    backend = _load_backend_service()
    ports = backend.get("ports")
    assert ports, (
        "Backend service has no `ports:` mapping — `curl localhost:8000/health` "
        "will fail. Issue #78 regression."
    )

    port_strs = [str(p) for p in ports]
    # Accept: "127.0.0.1:8000:8000" (preferred loopback-only) or
    # accept the loopback form as the canonical answer.
    has_loopback_8000 = any(
        re.match(r"^127\.0\.0\.1:8000:8000$", s.strip('"').strip("'"))
        for s in port_strs
    )
    assert has_loopback_8000, (
        f"Backend must publish 127.0.0.1:8000:8000 to keep the API on "
        f"loopback. Found ports: {port_strs}"
    )


def test_backend_port_is_loopback_only():
    """The published 8000 must NOT be bound to 0.0.0.0 — the API is internal."""
    backend = _load_backend_service()
    ports = backend.get("ports") or []
    port_strs = [str(p) for p in ports]

    for s in port_strs:
        normalized = s.strip('"').strip("'")
        # "8000:8000" without an IP host means 0.0.0.0 — forbidden
        if re.match(r"^8000:8000$", normalized):
            pytest.fail(
                f"Backend port '8000:8000' binds to all interfaces (0.0.0.0). "
                f"Use '127.0.0.1:8000:8000' to keep the API on the loopback "
                f"interface only."
            )
        # Also reject explicit "0.0.0.0:8000:8000"
        if re.match(r"^0\.0\.0\.0:8000:8000$", normalized):
            pytest.fail(
                f"Backend port '0.0.0.0:8000:8000' exposes the API to the "
                f"network. Use '127.0.0.1:8000:8000'."
            )
