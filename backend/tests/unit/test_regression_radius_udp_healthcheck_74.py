"""Regression test for issue #74: RADIUS healthcheck must probe UDP, not TCP.

The Linux healthcheck in \`docker-compose.linux.yml\` used \`nc -z -w2\`
which is a TCP probe. RADIUS auth binds UDP 1812 — nothing listens on
TCP 1812 — so the probe always exited 1 and the container stayed
\`unhealthy\` forever (and \`radius-syslog\`, which depends on the
backend reaching \`healthy\`, never got past \`Created\`).

Fix: add the \`-u\` flag so nc probes UDP. This test enforces the
contract on the source files so a future refactor cannot silently
revert to TCP.

The test also locks the port mapping itself (both compose files must
publish \`1812:1812/udp\` / \`1813:1813/udp\`, not TCP) because the
same class of bug — "the operator assumed TCP, RADIUS uses UDP" — is
easy to re-introduce in the port mapping too.
"""

import re
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]  # backend/tests/unit -> repo root


# ---------------------------------------------------------------------------
# docker-compose.linux.yml — healthcheck must use UDP probe
# ---------------------------------------------------------------------------


def _load_linux_compose_radius_block() -> str:
    """Return the raw text of the `radius:` block in docker-compose.linux.yml.

    Using the raw text (not yaml) because the block spans many lines and
    the healthcheck syntax uses an inline shell array that we want to
    assert against verbatim.
    """
    compose_path = REPO_ROOT / "docker-compose.linux.yml"
    in_block = False
    block_lines: list[str] = []

    for line in compose_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("radius:") and not stripped.startswith("radii"):
            in_block = True
            continue
        if in_block:
            # End of the block: a new top-level service or end-of-services
            if line and not line.startswith(" ") and stripped.endswith(":"):
                break
            block_lines.append(line)

    return "\n".join(block_lines)


def test_linux_healthcheck_uses_udp_flag():
    """The healthcheck must pass `-u` to nc so it probes UDP 1812."""
    block = _load_linux_compose_radius_block()
    assert "nc -z -u" in block or "nc -zu" in block, (
        "docker-compose.linux.yml radius healthcheck no longer uses the UDP "
        "flag (`-u`). The RADIUS auth port is UDP 1812 — a TCP probe will "
        "always fail and the container will never reach `healthy`. This is "
        "the original bug from issue #74."
    )
    # Also assert against the exact port we expect
    assert "1812" in block, "healthcheck must probe port 1812 (RADIUS auth)"


def test_linux_healthcheck_does_not_probe_tcp_only():
    """The old bug: `nc -z -w2 127.0.0.1 1812` (no -u) → TCP probe.

    Make sure the healthcheck string never appears in its broken form.
    """
    block = _load_linux_compose_radius_block()
    broken_pattern = re.compile(r"nc\s+-z\s+-w\d+\s+127\.0\.0\.1\s+1812(?!\s*\|)")
    assert not broken_pattern.search(block), (
        "Found a TCP-only nc probe (`nc -z -wN 127.0.0.1 1812` without `-u`). "
        "This is the original bug from #74 — the probe must include `-u` to "
        "match the UDP binding of FreeRADIUS auth."
    )


# ---------------------------------------------------------------------------
# Port mappings — must be UDP, not TCP
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "compose_filename,service_name",
    [
        ("docker-compose.yml", "radius"),
        ("docker-compose.linux.yml", "radius"),
    ],
)
def test_radius_ports_are_udp(compose_filename, service_name):
    """The RADIUS auth/acct ports must be published as UDP, not TCP."""
    compose_path = REPO_ROOT / compose_filename
    with compose_path.open() as fh:
        data = yaml.safe_load(fh)
    services = data.get("services", {})
    if service_name not in services:
        pytest.skip(f"{service_name} service not defined in {compose_filename}")
    ports = services[service_name].get("ports") or []
    port_strs = [str(p) for p in ports]

    # The published form must end with /udp (e.g. "1812:1812/udp").
    has_udp_1812 = any("1812:1812/udp" in s for s in port_strs)
    assert has_udp_1812, (
        f"{compose_filename} : service '{service_name}' must publish "
        f"1812:1812/udp. Found ports: {port_strs}"
    )
    # And the form WITHOUT /udp must NOT be present (1812:1812 alone = TCP).
    has_tcp_1812 = any(
        re.match(r"^\"?1812:1812\"?$", s.strip()) for s in port_strs
    )
    assert not has_tcp_1812, (
        f"{compose_filename} : service '{service_name}' publishes 1812:1812 "
        f"without /udp — that binds TCP. RADIUS auth is UDP, use 1812:1812/udp."
    )
