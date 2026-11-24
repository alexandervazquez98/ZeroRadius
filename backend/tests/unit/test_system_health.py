"""
Unit tests for container stats collection (#121, #128).

- Only containers of the backend's own compose project are listed.
- Per-container stats are fetched in parallel.
- Results are cached and concurrent callers share one Docker query.
"""

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import system_health

PROJECT_LABEL = "com.docker.compose.project"


def _fake_container(name, delay=0.0):
    c = MagicMock()
    c.id = f"{name}-0123456789"
    c.name = name
    c.attrs = {"State": {"Status": "running"}}
    c.labels = {PROJECT_LABEL: "zeroradius"}

    def stats(**_kwargs):
        time.sleep(delay)
        return {"memory_stats": {"usage": 1024 * 1024, "limit": 4 * 1024 * 1024}}

    c.stats.side_effect = stats
    return c


def _fake_client(containers, own_labels=None):
    client = MagicMock()
    client.containers.list.return_value = containers
    if own_labels is None:
        client.containers.get.side_effect = Exception("not running in a container")
    else:
        client.containers.get.return_value = SimpleNamespace(labels=own_labels)
    return client


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    system_health.clear_container_stats_cache()
    monkeypatch.delenv("COMPOSE_PROJECT_NAME", raising=False)
    yield
    system_health.clear_container_stats_cache()


def test_lists_only_containers_of_own_compose_project():
    client = _fake_client([_fake_container("radius-backend")], own_labels={PROJECT_LABEL: "zeroradius"})
    with patch.object(system_health.docker, "from_env", return_value=client):
        result = system_health.get_container_stats()

    client.containers.list.assert_called_once_with(
        all=True, filters={"label": f"{PROJECT_LABEL}=zeroradius"}
    )
    assert [c.name for c in result] == ["radius-backend"]


def test_compose_project_name_env_overrides_detection(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "zr-prod")
    client = _fake_client([], own_labels={PROJECT_LABEL: "other"})
    with patch.object(system_health.docker, "from_env", return_value=client):
        system_health.get_container_stats()

    client.containers.list.assert_called_once_with(
        all=True, filters={"label": f"{PROJECT_LABEL}=zr-prod"}
    )


def test_unknown_project_lists_nothing_instead_of_every_host_container():
    client = _fake_client([_fake_container("unrelated")], own_labels=None)
    with patch.object(system_health.docker, "from_env", return_value=client):
        result = system_health.get_container_stats()

    assert result == []
    client.containers.list.assert_not_called()


def test_container_stats_are_fetched_in_parallel():
    containers = [_fake_container(f"radius-{i}", delay=0.4) for i in range(4)]
    client = _fake_client(containers, own_labels={PROJECT_LABEL: "zeroradius"})
    with patch.object(system_health.docker, "from_env", return_value=client):
        started = time.perf_counter()
        result = system_health.get_container_stats()
        elapsed = time.perf_counter() - started

    assert len(result) == 4
    assert elapsed < 1.0, f"4 x 0.4s stats took {elapsed:.2f}s (sequential?)"


def test_results_are_cached_within_ttl():
    client = _fake_client([_fake_container("radius-backend")], own_labels={PROJECT_LABEL: "zeroradius"})
    with patch.object(system_health.docker, "from_env", return_value=client) as from_env:
        first = system_health.get_container_stats()
        second = system_health.get_container_stats()

    assert first == second
    assert from_env.call_count == 1


def test_concurrent_callers_share_one_docker_query():
    client = _fake_client([_fake_container("radius-backend", delay=0.3)],
                          own_labels={PROJECT_LABEL: "zeroradius"})
    results = []
    with patch.object(system_health.docker, "from_env", return_value=client) as from_env:
        threads = [threading.Thread(target=lambda: results.append(system_health.get_container_stats()))
                   for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert from_env.call_count == 1
    assert len(results) == 5 and all(r == results[0] for r in results)


def test_docker_network_error_returns_empty_and_is_cached():
    import requests

    client = _fake_client([], own_labels={PROJECT_LABEL: "zeroradius"})
    client.containers.list.side_effect = requests.exceptions.ReadTimeout("docker hung")
    with patch.object(system_health.docker, "from_env", return_value=client) as from_env:
        assert system_health.get_container_stats() == []
        assert system_health.get_container_stats() == []

    from_env.assert_called_once_with(timeout=system_health.DOCKER_TIMEOUT)
    client.close.assert_called_once()
