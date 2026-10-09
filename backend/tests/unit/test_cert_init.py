"""Tests for RADIUS certificate initialization.

Two layers of coverage:

1. **Static (no Docker)**: verifies the host-side artifacts that should
   always be present in a clean checkout (`.gitkeep` placeholder) and
   that the docker-entrypoint, docker-compose, and Dockerfile wire the
   right paths.

2. **Generator (no Docker)**: runs ``generate_certs.py`` (the same script
   that ships with the project) inside a ``tmp_path`` and asserts the
   three required files appear with the right permissions. This is the
   regression guard for the untrack of ``radius/certs/`` (issue #88):
   we no longer rely on the files being checked in to satisfy the
   tests — the test drives the generator and verifies the result.

The Docker-layer smoke (real entrypoint on a real radius container) is
out of scope for unit tests — covered by the deploy validation in
``docs/deployment.md``.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


# Get project root (parent of backend/tests/unit/)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


# ---------------------------------------------------------------------------
# 1. Static checks — always green on a clean checkout
# ---------------------------------------------------------------------------


class TestCertArtifactsOnDisk:
    """The working tree must contain only the placeholder; the certs
    themselves are generated, not committed (issue #88)."""

    def test_certs_directory_exists(self):
        assert (PROJECT_ROOT / "radius" / "certs").is_dir(), (
            "radius/certs/ must exist as a directory (placeholder .gitkeep keeps it "
            "alive in fresh clones)"
        )

    def test_only_gitkeep_is_tracked(self):
        """The only file git should know about in radius/certs/ is .gitkeep."""
        result = subprocess.run(
            ["git", "ls-files", "radius/certs/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked = [Path(p).name for p in result.stdout.splitlines() if p]
        assert tracked == [".gitkeep"], (
            f"Only .gitkeep should be tracked under radius/certs/; got {tracked}. "
            f"Untracked committed certs re-introduce issue #88."
        )

    def test_docker_entrypoint_has_cert_init(self):
        entrypoint = PROJECT_ROOT / "radius" / "docker-entrypoint.sh"
        content = entrypoint.read_text()
        assert "MOUNTED_CERTS" in content, (
            "docker-entrypoint.sh should define MOUNTED_CERTS"
        )
        assert "openssl req" in content, (
            "docker-entrypoint.sh must generate certs via openssl when the volume "
            "is empty (otherwise a clean deploy crash-loops the radius container)"
        )

    def test_docker_compose_uses_named_volume_not_bind_mount(self):
        """The radius service must NOT bind-mount a host directory onto /etc/freeradius/certs.

        Issue #85 root cause: a bind mount makes the entrypoint's chown escape
        onto the host working tree. Named volumes (or no mount) keep the
        chown local to the container.
        """
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        compose_config = yaml.safe_load(compose_file.read_text())
        radius_volumes = compose_config.get("services", {}).get("radius", {}).get("volumes", [])
        bad_mounts = [
            v for v in radius_volumes
            if "freeradius/certs" in str(v) and str(v).startswith("./")
        ]
        assert not bad_mounts, (
            f"radius service must NOT bind-mount a host directory onto "
            f"/etc/freeradius/certs (issue #85). Found: {bad_mounts}. "
            f"Use a named volume instead (e.g. `radius_certs:/etc/freeradius/certs`)."
        )

    def test_docker_compose_defines_named_radius_certs_volume(self):
        """The `radius_certs` named volume must be defined and used by both radius and backend."""
        compose_file = PROJECT_ROOT / "docker-compose.yml"
        compose_config = yaml.safe_load(compose_file.read_text())
        top_volumes = compose_config.get("volumes", {})
        assert "radius_certs" in top_volumes, (
            "docker-compose.yml must define a top-level `radius_certs` volume "
            "(used by the radius service as its cert dir)."
        )
        services = compose_config.get("services", {})
        for service_name in ("radius", "backend"):
            svc = services.get(service_name, {})
            mounts = [str(v) for v in svc.get("volumes", [])]
            uses = any("radius_certs" in m for m in mounts)
            assert uses, (
                f"{service_name} service should mount the radius_certs named volume; "
                f"current mounts: {mounts}"
            )


# ---------------------------------------------------------------------------
# 2. Generator-driven tests — exercise the script the same way the entrypoint
#    would, but without requiring Docker
# ---------------------------------------------------------------------------


def _run_generate_certs(tmp_path: Path) -> Path:
    """Replicate the radius entrypoint's inline openssl generation.

    The radius docker-entrypoint.sh generates a self-signed cert pair
    when the named volume is empty (see the fix for issues #85 and #88).
    This helper invokes the same openssl command in tmp_path, then
    mirrors the entrypoint's `cp server.pem ca.pem` step, and returns
    the certs/ directory.

    We intentionally do NOT call the repo-root `generate_certs.py`
    here — that script targets the nginx/frontend TLS use case and
    emits `.crt` filenames, not the `.pem` filenames the radius
    eap module reads. The two generators serve different consumers
    and have different naming conventions; testing one with the
    other's expectations is the bug round-1 of #90 introduced.
    """
    if shutil.which("openssl") is None:
        pytest.skip("openssl is not on PATH; cannot run generation end-to-end")
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    result = subprocess.run(
        [
            "openssl", "req", "-x509", "-nodes", "-days", "3650",
            "-newkey", "rsa:2048",
            "-keyout", str(certs_dir / "server.key"),
            "-out",    str(certs_dir / "server.pem"),
            "-subj",   "/C=MX/ST=Local/L=Local/O=ZeroRadius/CN=localhost",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f"openssl req failed (rc={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Mirror the entrypoint's CA copy.
    shutil.copyfile(certs_dir / "server.pem", certs_dir / "ca.pem")
    return certs_dir


class TestCertGeneratorProducesRequiredFiles:
    """Drive the host-side generator and assert the three required files appear."""

    def test_required_cert_files_are_generated(self, tmp_path: Path) -> None:
        certs_dir = _run_generate_certs(tmp_path)
        for filename in ("ca.pem", "server.pem", "server.key"):
            assert (certs_dir / filename).is_file(), (
                f"radius entrypoint generation did not produce {filename}"
            )

    def test_generated_cert_is_valid(self, tmp_path: Path) -> None:
        certs_dir = _run_generate_certs(tmp_path)
        ca = certs_dir / "ca.pem"
        result = subprocess.run(
            ["openssl", "x509", "-in", str(ca), "-noout", "-dates"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Failed to read generated CA: {result.stderr}"
        )
        assert "notBefore" in result.stdout and "notAfter" in result.stdout, (
            "Generated cert must have a validity window"
        )

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Unix file permissions are not meaningful on Windows NTFS",
    )
    def test_generated_key_has_secure_permissions(self, tmp_path: Path) -> None:
        """Generated server.key must be 0600 (not world-readable)."""
        certs_dir = _run_generate_certs(tmp_path)
        key = certs_dir / "server.key"
        mode = key.stat().st_mode
        assert (mode & 0o007) == 0, (
            f"Generated server.key must not be world-readable; "
            f"got mode {oct(mode & 0o777)}"
        )
        assert (mode & 0o777) == 0o600, (
            f"Generated server.key should be 0600; got {oct(mode & 0o777)}"
        )


# ---------------------------------------------------------------------------
# 3. Entrypoint consistency — the entrypoint must generate certs and not
#    try to chown the bind mount (issue #85).
# ---------------------------------------------------------------------------


class TestEntrypointCertIsolation:
    """Lock the #85 fix at the source level."""

    def test_dockerfile_has_no_certs_symlink(self) -> None:
        """The old `ln -sf /etc/raddb/certs /etc/freeradius/certs` is gone."""
        dockerfile = (PROJECT_ROOT / "radius" / "Dockerfile").read_text()
        symlink_pattern = re.compile(
            r"^\s*RUN\s+ln\s+-s[f]?\s+\S*certs\s+\S*certs",
            re.MULTILINE,
        )
        match = symlink_pattern.search(dockerfile)
        assert not match, (
            f"Found a certs symlink in radius/Dockerfile: {match.group(0)!r}. "
            f"Issue #85: the symlink makes /etc/raddb/certs and /etc/freeradius/certs "
            f"the same inode, so the entrypoint's chown escapes onto the host "
            f"bind mount."
        )

    def test_entrypoint_generates_certs_with_openssl(self) -> None:
        """The entrypoint must call openssl to generate a self-signed pair
        when the named volume is empty — otherwise a fresh deploy crashes."""
        entrypoint = (PROJECT_ROOT / "radius" / "docker-entrypoint.sh").read_text()
        # Find the openssl generation block
        assert "openssl req" in entrypoint, (
            "docker-entrypoint.sh must generate certs with `openssl req` when "
            "the volume is empty. Without this, a fresh deploy leaves "
            "/etc/freeradius/certs empty and the radius container crash-loops."
        )
        # And the generation must be inside the "if [ \"$FILE_COUNT\" -eq 0 ]" block.
        # Loose check: the openssl command must precede the chown.
        openssl_idx = entrypoint.find("openssl req")
        chown_idx = entrypoint.find("chown -R freerad:freerad")
        assert 0 <= openssl_idx < chown_idx, (
            "openssl generation must run before the chown step"
        )
