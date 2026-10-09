"""
RADIUS protocol tests — Huntgroup enforcement (closes #92).

These tests lock the contract documented in
`docs/01-nas-provisioning.md` §2: a `radgroupcheck` row whose
`NAS-IP-Address` value does not match the request must cause
`Access-Reject` (not silent `Access-Accept` with stripped reply
attributes).

Red/Green expectations (Round 2 — explicit unlang policy):

    +--------------------------------+----------------+----------------+
    | Scenario                       | on `main`      | after fix      |
    +--------------------------------+----------------+----------------+
    | matching NAS, with reply attrs | GREEN (accept) | GREEN (accept) |
    | mismatching NAS                | RED (accept!!) | GREEN (reject) |
    | group without radgroupcheck    | GREEN (accept) | GREEN (accept) |
    | user via access_policy only    | GREEN (accept) | GREEN (accept) |
    +--------------------------------+----------------+----------------+

Round 1 mislabeled the scenario 4 test as
`test_user_without_group_returns_accept`. The correct name, given that
`carlos.ruiz` IS assigned to `branch-read` via
`access_policy_assignments` (just not via `radusergroup`), is
`test_user_with_policy_assigned_group_no_radusergroup_returns_accept`.

Convention notes:

- All tests use `skip_if_no_radius` for "no server" (a server-side
  problem; the harness must report it as skip, not fail).
- No silent swallowing of network timeouts inside the request body. A
  timeout against a server we have confirmed is reachable IS a failure
  of the system under test and must propagate (this was the
  silent-green bug that caused Round 1 to merge a no-op fix).
- Tests rely on the seed fixture
  `radius-tests/fixtures/seed_huntgroup_enforcement.sql` which includes
  the three `nas` table entries (127.0.0.1, 192.168.1.10,
  192.168.1.50) so FreeRADIUS does not drop the request before
  reaching `nas_based_authorization`.
"""

import pytest
from pyrad import packet

from conftest import parse_reply_attributes, reply_contains_marker, send_access_request

pytestmark = pytest.mark.radius


def _cisco_avpair_values(attrs: dict[str, list[str]]) -> list[str]:
    """Return all Cisco-AVPair values from the parsed reply (vendor=9, attr=1)."""
    return attrs.get("Cisco-AVPair", [])


class TestHuntgroupEnforcement:
    """Round 2 huntgroup-enforcement contract (closes #92)."""

    @pytest.mark.radius
    def test_matching_nas_returns_accept_with_reply_attrs(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 1: juan.perez + oficina-admin (radgroupcheck NAS-IP=192.168.1.10)
        + request from 192.168.1.10 -> Access-Accept with Cisco-AVPair reply.

        GREEN on `main` and GREEN after the fix (the hydration order test).
        If the new policy is wired BEFORE the second -sql, this test will
        FAIL because `radgroupreply` attributes won't be present.
        """
        reply = send_access_request(
            radius_client,
            username="juan.perez",
            password="testpassword",
            nas_ip="192.168.1.10",
        )

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept, got code {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        # Reply-Message from radgroupreply must be hydrated.
        assert reply_contains_marker(reply, "HUNTGROUP-OFICINA-ADMIN"), (
            "radgroupreply Reply-Message for oficina-admin not hydrated; "
            "the new policy may be running before the second -sql pass."
        )
        # Cisco-AVPair shell:priv-lvl=15 must be present in Access-Accept.
        avpairs = _cisco_avpair_values(attrs)
        assert any("shell:priv-lvl=15" in v for v in avpairs), (
            f"Expected Cisco-AVPair shell:priv-lvl=15 in reply, got {avpairs}"
        )

    @pytest.mark.radius
    def test_mismatching_nas_returns_reject(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 2: juan.perez + oficina-admin (radgroupcheck NAS-IP=192.168.1.10)
        + request from 192.168.1.50 -> Access-Reject, no Cisco-AVPair.

        RED on `main` (the bug — current behavior is Access-Accept with
        stripped reply attrs).
        GREEN after the fix (the new policy rejects via Reply-Message
        "Huntgroup check failed: ...").
        """
        reply = send_access_request(
            radius_client,
            username="juan.perez",
            password="testpassword",
            nas_ip="192.168.1.50",
        )

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject for mismatching NAS-IP, got code {reply.code}. "
            "If this is Access-Accept, the huntgroup enforcement policy is not wired."
        )
        attrs = parse_reply_attributes(reply)
        avpairs = _cisco_avpair_values(attrs)
        assert not any("shell:priv-lvl=15" in v for v in avpairs), (
            f"Reject path leaked Cisco-AVPair: {avpairs}"
        )
        # Distinct Reply-Message distinguishes this from nas_based_authorization's
        # reject path (design.md §D5).
        assert reply_contains_marker(
            reply, "Huntgroup check failed: NAS-IP-Address does not match group rule"
        ), "Distinct Reply-Message for huntgroup reject path is missing"

    @pytest.mark.radius
    def test_group_without_check_returns_accept(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 3: maria.lopez + branch-read (no radgroupcheck rows)
        + request from 192.168.1.50 -> Access-Accept (regression guard).

        GREEN on `main` and GREEN after the fix — the policy must skip
        enforcement when the resolved group has no radgroupcheck rows.
        """
        reply = send_access_request(
            radius_client,
            username="maria.lopez",
            password="testpassword",
            nas_ip="192.168.1.50",
        )

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for group with no radgroupcheck, "
            f"got code {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        assert reply_contains_marker(reply, "HUNTGROUP-BRANCH-READ")
        avpairs = _cisco_avpair_values(attrs)
        assert any("shell:priv-lvl=1" in v for v in avpairs), (
            f"Expected Cisco-AVPair shell:priv-lvl=1 in reply, got {avpairs}"
        )

    @pytest.mark.radius
    def test_user_with_policy_assigned_group_no_radusergroup_returns_accept(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 4: carlos.ruiz has NO radusergroup row but is assigned to
        branch-read via access_policy_assignments. branch-read has no
        radgroupcheck rows. Request from 192.168.1.50 -> Access-Accept.

        GREEN on `main` and GREEN after the fix — the
        access_policy_assignments path resolves SQL-Group to
        branch-read; the policy-assignment path is unchanged from v1.3.4.

        Round 1 mislabeled this test
        `test_user_without_group_returns_accept` (the user IS in a group;
        the missing thing is the `radusergroup` row, not the group
        membership). The corrected name documents the actual scenario.
        """
        reply = send_access_request(
            radius_client,
            username="carlos.ruiz",
            password="testpassword",
            nas_ip="192.168.1.50",
        )

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept for user assigned via "
            f"access_policy_assignments (no radusergroup), got code {reply.code}"
        )
        attrs = parse_reply_attributes(reply)
        assert reply_contains_marker(reply, "HUNTGROUP-BRANCH-READ")
        avpairs = _cisco_avpair_values(attrs)
        assert any("shell:priv-lvl=1" in v for v in avpairs), (
            f"Expected Cisco-AVPair shell:priv-lvl=1 in reply, got {avpairs}"
        )
