"""Regression test for issue #98: the huntgroup seed must not collide with real NAS.

``radius-tests/fixtures/seed_huntgroup_enforcement.sql`` inserted ``nas``
rows at 192.168.1.10 / 192.168.1.50 with ``ON DUPLICATE KEY UPDATE``. Since
``nas.nasname`` has no unique index the upsert never fired, so running the
seed against a persistent database that already had a real NAS at one of
those addresses created a second client definition for it (secret
``testing123``), which can break authentication for the real device.

Contract enforced here:

1. Seeded NAS addresses are loopback or TEST-NET-1 (192.0.2.0/24, RFC 5737),
   which no real device uses.
2. Each ``nas`` row is inserted only if no row with that ``nasname`` exists
   (no reliance on a unique key that does not exist).
3. The RADIUS tests send the same NAS-IP-Address values the seed declares,
   and every ``access_policy_assignments.target_key`` encodes its IP with the
   correct length prefix.
"""

from __future__ import annotations

import ipaddress
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SEED = REPO_ROOT / "radius-tests" / "fixtures" / "seed_huntgroup_enforcement.sql"
TESTS = REPO_ROOT / "radius-tests" / "test_radius_huntgroup_enforcement.py"
TEST_NET_1 = ipaddress.ip_network("192.0.2.0/24")
LOOPBACK = ipaddress.ip_address("127.0.0.1")


def _seed() -> str:
    return SEED.read_text()


def _seeded_nas_addresses() -> list[str]:
    # INSERT INTO nas (...) SELECT '<ip>', ... WHERE NOT EXISTS (... nasname = '<ip>')
    return re.findall(r"INSERT INTO nas\b.*?SELECT\s+'([^']+)'", _seed(), re.S)


def test_regression_seed_nas_addresses_cannot_collide_with_real_devices():
    addresses = _seeded_nas_addresses()
    assert addresses, "seed must still declare the nas rows the tests need"
    for raw in addresses:
        ip = ipaddress.ip_address(raw)
        assert ip == LOOPBACK or ip in TEST_NET_1, (
            f"seeded NAS {raw} could collide with a real device; use 192.0.2.0/24"
        )


def test_regression_seed_does_not_rely_on_nonexistent_unique_key():
    seed = _seed()
    assert "ON DUPLICATE KEY" not in seed, (
        "nas.nasname has no unique index, so ON DUPLICATE KEY never fires (#98)"
    )
    inserts = re.findall(r"INSERT INTO nas\b.*?;", seed, re.S)
    assert len(inserts) == len(_seeded_nas_addresses())
    for stmt in inserts:
        address = re.search(r"SELECT\s+'([^']+)'", stmt).group(1)
        assert re.search(
            rf"WHERE NOT EXISTS\s*\(\s*SELECT 1 FROM nas WHERE nasname = '{re.escape(address)}'\s*\)",
            stmt,
        ), f"nas insert for {address} must be skipped when that address already exists"


def test_tests_use_the_seeded_nas_addresses():
    sent = set(re.findall(r'nas_ip="([^"]+)"', TESTS.read_text()))
    assert sent, "huntgroup tests must send an explicit NAS-IP-Address"
    assert sent <= set(_seeded_nas_addresses())


def test_target_keys_encode_ip_with_correct_length_prefix():
    keys = re.findall(r"CONCAT\('[^|]+\|(\d+):([^|]+)\|", _seed())
    assert keys
    for length, ip in keys:
        assert int(length) == len(ip), f"target_key prefix {length} does not match {ip}"
        assert ipaddress.ip_address(ip) in TEST_NET_1
