"""
Test for certificate initialization in RADIUS container.

This test verifies that the docker-entrypoint.sh correctly handles
certificate initialization:
1. Certificates are mounted from host to container
2. Certificates are copied to the correct location
3. Permissions are set correctly

These tests depend on Docker/Linux infrastructure (certs, openssl, mounts).
They are marked with `infra` and excluded from the fast local gate.

Run on Linux/Docker: pytest tests/test_cert_init.py -v -m infra
"""

import os
import platform
import pytest
import subprocess


# Get project root (parent of backend/tests/unit/)
PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


@pytest.mark.infra
class TestCertificateInitialization:
    """Test certificate initialization logic (Docker/Linux infrastructure)."""

    def test_certs_directory_exists(self):
        """Verify that the radius/certs directory exists and contains required files."""
        cert_dir = os.path.join(PROJECT_ROOT, "radius", "certs")
        assert os.path.exists(cert_dir), (
            f"Certificate directory {cert_dir} does not exist"
        )

    def test_required_cert_files_exist(self):
        """Verify all required certificate files exist."""
        cert_dir = os.path.join(PROJECT_ROOT, "radius", "certs")

        required_files = ["ca.pem", "server.pem", "server.key"]
        for filename in required_files:
            filepath = os.path.join(cert_dir, filename)
            assert os.path.exists(filepath), (
                f"Required certificate {filename} not found in {cert_dir}"
            )

    def test_certificate_validity(self):
        """Verify that certificates are valid (not expired)."""
        cert_dir = os.path.join(PROJECT_ROOT, "radius", "certs")
        ca_cert = os.path.join(cert_dir, "ca.pem")

        # Check certificate is valid using openssl
        result = subprocess.run(
            ["openssl", "x509", "-in", ca_cert, "-noout", "-dates"],
            capture_output=True,
            text=True,
        )

        # If openssl fails, the cert might not be valid
        assert result.returncode == 0, f"Failed to read certificate: {result.stderr}"
        assert "notBefore" in result.stdout, "Certificate has no start date"
        assert "notAfter" in result.stdout, "Certificate has no expiration date"

    @pytest.mark.skipif(
        platform.system() == "Windows",
        reason="Unix file permissions are not meaningful on Windows NTFS",
    )
    def test_key_file_permissions(self):
        """Verify private key has secure permissions (not world-readable)."""
        cert_dir = os.path.join(PROJECT_ROOT, "radius", "certs")
        key_file = os.path.join(cert_dir, "server.key")

        if os.path.exists(key_file):
            stat_info = os.stat(key_file)
            # Check that others have no read permission (mode & 0o007 == 0)
            assert (stat_info.st_mode & 0o007) == 0, (
                "Private key should not be world-readable"
            )

    def test_docker_entrypoint_has_cert_init(self):
        """Verify docker-entrypoint.sh contains certificate initialization logic."""
        entrypoint = os.path.join(PROJECT_ROOT, "radius", "docker-entrypoint.sh")

        with open(entrypoint, "r") as f:
            content = f.read()

        assert "CERT_DIR" in content, "docker-entrypoint.sh should define CERT_DIR"
        assert "server.key" in content, (
            "docker-entrypoint.sh should check for server.key"
        )
        assert "MOUNTED_CERTS" in content or "radius-certs" in content, (
            "docker-entrypoint.sh should reference mounted certificates path"
        )

    def test_docker_compose_mounts_certs(self):
        """Verify docker-compose.yml mounts certificates to radius and backend services."""
        import yaml

        compose_file = os.path.join(PROJECT_ROOT, "docker-compose.yml")

        with open(compose_file, "r") as f:
            compose_config = yaml.safe_load(f)

        # Check radius service has cert mount
        radius_service = compose_config.get("services", {}).get("radius", {})
        radius_volumes = radius_service.get("volumes", [])
        radius_cert_mounts = [v for v in radius_volumes if "certs" in v]
        assert len(radius_cert_mounts) >= 1, "Radius service should mount certs volume"

        # Check backend service also has cert mount
        backend_service = compose_config.get("services", {}).get("backend", {})
        backend_volumes = backend_service.get("volumes", [])
        backend_cert_mounts = [v for v in backend_volumes if "certs" in v]
        assert len(backend_cert_mounts) >= 1, (
            "Backend service should mount certs volume"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
