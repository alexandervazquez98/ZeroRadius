"""
System Health Service — Docker containers and host system resources.
Provides container stats and system resource monitoring using Docker SDK and psutil.
"""

import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

import docker

logger = logging.getLogger(__name__)

# Cache duration in seconds
CACHE_TTL = 10


@dataclass
class ContainerStats:
    id: str
    name: str
    status: str
    state: str
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_mb: float
    network_tx_mb: float


@dataclass
class SystemResources:
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    network_interfaces: list[str]


def _parse_docker_stats(container) -> Optional[ContainerStats]:
    """Parse Docker stats for a single container."""
    try:
        stats = container.stats(stream=False)

        # Container ID and name
        container_id = container.id[:12]
        container_name = container.name.lstrip("/")

        # Status and state
        state = container.attrs.get("State", {})
        status = state.get("Status", "unknown")
        running_state = state.get("OciState", {}).get("Status", status)

        # CPU calculation
        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})
        cpu_delta = cpu_stats.get("cpu_usage", {}).get(
            "total_usage", 0
        ) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get(
            "system_cpu_usage", 0
        )
        cpu_count = cpu_stats.get("online_cpus", 1) or 1

        cpu_percent = 0.0
        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * cpu_count * 100.0

        # Memory
        mem_stats = stats.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit > 0 else 0.0

        # Network I/O
        networks = stats.get("networks", {})
        rx_bytes = sum((net.get("rx_bytes", 0) for net in networks.values()), 0)
        tx_bytes = sum((net.get("tx_bytes", 0) for net in networks.values()), 0)

        return ContainerStats(
            id=container_id,
            name=container_name,
            status=status,
            state=running_state,
            cpu_percent=round(cpu_percent, 2),
            memory_usage_mb=round(mem_usage / (1024 * 1024), 2),
            memory_limit_mb=round(mem_limit / (1024 * 1024), 2),
            memory_percent=round(mem_percent, 2),
            network_rx_mb=round(rx_bytes / (1024 * 1024), 2),
            network_tx_mb=round(tx_bytes / (1024 * 1024), 2),
        )
    except Exception as e:
        logger.warning("Failed to get stats for container %s: %s", container.name, e)
        return None


def get_container_stats() -> list[ContainerStats]:
    """
    Get stats for all Docker containers.
    Returns list of ContainerStats with CPU, memory, and network metrics.
    """
    try:
        client = docker.from_env()
        containers = client.containers.list(all=True)

        results = []
        for container in containers:
            stats = _parse_docker_stats(container)
            if stats:
                results.append(stats)

        client.close()
        return results
    except docker.errors.DockerException as e:
        logger.error("Failed to connect to Docker: %s", e)
        return []


def get_system_resources() -> SystemResources:
    """
    Get host system resources using psutil.
    Returns CPU, memory, disk, and network metrics.
    """
    try:
        import psutil
    except ImportError:
        logger.error("psutil not installed")
        return SystemResources(
            cpu_percent=0.0,
            cpu_count=0,
            memory_total_gb=0.0,
            memory_used_gb=0.0,
            memory_percent=0.0,
            disk_total_gb=0.0,
            disk_used_gb=0.0,
            disk_percent=0.0,
            network_interfaces=[],
        )

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count = psutil.cpu_count(logical=True) or 1

    # Memory
    mem = psutil.virtual_memory()
    memory_total_gb = round(mem.total / (1024**3), 2)
    memory_used_gb = round(mem.used / (1024**3), 2)
    memory_percent = mem.percent

    # Disk
    try:
        disk = psutil.disk_usage("/")
        disk_total_gb = round(disk.total / (1024**3), 2)
        disk_used_gb = round(disk.used / (1024**3), 2)
        disk_percent = disk.percent
    except Exception:
        disk_total_gb = 0.0
        disk_used_gb = 0.0
        disk_percent = 0.0

    # Network interfaces
    net_ifaces = list(psutil.net_if_stats().keys())

    return SystemResources(
        cpu_percent=round(cpu_percent, 1),
        cpu_count=cpu_count,
        memory_total_gb=memory_total_gb,
        memory_used_gb=memory_used_gb,
        memory_percent=round(memory_percent, 1),
        disk_total_gb=disk_total_gb,
        disk_used_gb=disk_used_gb,
        disk_percent=round(disk_percent, 1),
        network_interfaces=net_ifaces,
    )
