"""
Integration tests: root / and /system/ntp-status endpoints.

Verifies:
- GET / is public and returns 200 with a welcome message
- GET /system/ntp-status requires admin or superadmin
- helpdesk cannot access ntp-status (403)
"""

import pytest


class TestRootEndpoint:
    """GET / — public health check."""

    async def test_root_returns_200(self, async_client):
        resp = await async_client.get("/")
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestSystemNTPStatus:
    """GET /system/ntp-status — admin/superadmin only."""

    async def test_superadmin_can_read_ntp_status(self, async_client, superadmin_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # 200 if ntpd/chrony is available; service may return 200 even without
        # an actual NTP daemon (ntp_status service handles gracefully)
        assert resp.status_code == 200

    async def test_admin_can_read_ntp_status(self, async_client, admin_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    async def test_helpdesk_cannot_read_ntp_status(self, async_client, helpdesk_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {helpdesk_token}"},
        )
        assert resp.status_code == 403

    async def test_readonly_cannot_read_ntp_status(self, async_client, readonly_token):
        resp = await async_client.get(
            "/system/ntp-status",
            headers={"Authorization": f"Bearer {readonly_token}"},
        )
        assert resp.status_code == 403

    async def test_unauthenticated_cannot_read_ntp_status(self, async_client):
        resp = await async_client.get("/system/ntp-status")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# System health endpoints (#121, #128)
# ---------------------------------------------------------------------------
import asyncio
import time
from unittest.mock import patch

from app.services.system_health import ContainerStats, SystemResources


def _container(name: str) -> ContainerStats:
    return ContainerStats(
        id="abc123def456", name=name, status="running", state="running",
        cpu_percent=1.5, memory_usage_mb=80.0, memory_limit_mb=2000.0,
        memory_percent=4.0, network_rx_mb=1.0, network_tx_mb=2.0,
    )


_RESOURCES = SystemResources(
    cpu_percent=10.0, cpu_count=2, memory_total_gb=2.0, memory_used_gb=1.0,
    memory_percent=50.0, disk_total_gb=100.0, disk_used_gb=10.0,
    disk_percent=10.0, network_interfaces=["eth0"],
)


class TestSystemHealthContainers:
    async def test_regression_containers_endpoint_returns_200_121(self, async_client, admin_token):
        with patch("app.routers.system.get_container_stats",
                   return_value=[_container("radius-backend"), _container("radius-db")]):
            resp = await async_client.get(
                "/system/health/containers",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["running"] == 2
        assert [c["name"] for c in body["containers"]] == ["radius-backend", "radius-db"]


class TestSystemHealthDoesNotBlockEventLoop:
    """A slow health call must not delay other requests (#128)."""

    @pytest.mark.parametrize("path,target,value", [
        ("/system/health/containers", "app.routers.system.get_container_stats", []),
        ("/system/health/resources", "app.routers.system.get_system_resources", _RESOURCES),
    ])
    async def test_regression_slow_health_call_does_not_block_other_requests_128(
        self, async_client, admin_token, path, target, value
    ):
        def slow(*_args, **_kwargs):
            time.sleep(1.0)
            return value

        with patch(target, side_effect=slow):
            started = time.perf_counter()
            slow_request = asyncio.create_task(async_client.get(
                path, headers={"Authorization": f"Bearer {admin_token}"},
            ))
            await asyncio.sleep(0.1)  # let the slow request start
            fast = await async_client.get("/")
            fast_done = time.perf_counter() - started
            slow_resp = await slow_request

        assert fast.status_code == 200
        assert slow_resp.status_code == 200
        # Blocking the event loop would push this past the 1 s slow call.
        assert fast_done < 0.6, f"GET / finished {fast_done:.2f}s after {path} started"
