"""RADIUS protocol tests — huntgroup enforcement (closes #92).

Locks the four spec scenarios from
`openspec/changes/huntgroup-enforcement/specs/huntgroup-enforcement/spec.md`:

1. Group with radgroupcheck + matching NAS-IP-Address  → Access-Accept with reply attrs
2. Group with radgroupcheck + non-matching NAS-IP-Address → Access-Reject
3. Group with NO radgroupcheck rows (regression guard) → Access-Accept
4. User with NO radusergroup (regression guard)          → Access-Accept

Tests are marked `@pytest.mark.radius` and use the `skip_if_no_radius` fixture
so they auto-skip on hosts without a FreeRADIUS server. The expected RED/GREEN
on the unfixed `radius/default.conf` (master) is:

- test_matching_nas_returns_accept_with_reply_attrs  → currently passes (GREEN)
- test_mismatching_nas_returns_reject               → currently FAILS (RED — the bug)
- test_group_without_check_returns_accept            → currently passes (GREEN)
- test_user_without_group_returns_accept             → currently passes (GREEN)

After the config flip (`-sql` → `sql` on line 441) all four turn GREEN.
"""

import pytest
from pyrad import packet
from pyrad.client import Timeout

pytestmark = pytest.mark.radius


# ---------------------------------------------------------------------------
# Constants from the deterministic seed
# (radius-tests/fixtures/seed_huntgroup_enforcement.sql)
# ---------------------------------------------------------------------------

# Group with a radgroupcheck row (NAS-IP-Address == 192.168.1.10)
GROUP_WITH_CHECK = "grp_huntgroup_oficina_admin"
PRIV_LVL_15_MARKER = "shell:priv-lvl=15"

# Group with NO radgroupcheck rows (regression guard)
GROUP_WITHOUT_CHECK = "grp_huntgroup_branch_read"
PRIV_LVL_1_MARKER = "shell:priv-lvl=1"

# User with a group that has a check rule
USER_IN_CHECKED_GROUP = "juan.perez"

# User with a group that has no check rule
USER_IN_UNCHECKED_GROUP = "maria.lopez"

# User with NO radusergroup row
USER_WITHOUT_GROUP = "carlos.ruiz"

# NAS-IPs from the spec scenarios
NAS_MATCHING = "192.168.1.10"      # matches oficina-admin check rule
NAS_MISMATCHING = "192.168.1.50"   # does NOT match oficina-admin check rule

PASSWORD = "testpassword"


def _send_access_request(client, username: str, password: str, nas_ip: str):
    """Build and send an Access-Request to a specific NAS-IP-Address."""
    req = client.CreateAuthPacket(
        code=packet.AccessRequest,
        User_Name=username,
    )
    req["User-Password"] = req.PwCrypt(password)
    req["NAS-IP-Address"] = nas_ip
    req["NAS-Port"] = 0
    return client.SendPacket(req)


def _reply_contains_avpair_marker(reply, marker: str) -> bool:
    """Return True if `marker` (e.g. "shell:priv-lvl=15") is present in the reply.

    The Cisco-AVPair VSA is nested inside Vendor-Specific (attr 26). The reply
    may surface it via `parse_reply_attributes` keys "Cisco-AVPair" or it may
    still be wrapped; we also fall back to a raw string scan to be robust
    against the local pyrad dictionary.
    """
    # Fast path: parsed attributes
    for key in reply.keys():
        try:
            values = reply[key]
        except Exception:
            continue
        joined = " ".join(str(v) for v in values) if isinstance(values, (list, tuple)) else str(values)
        if marker in joined:
            return True
        # Also scan the attribute name itself in case the value is bytes
        if marker in str(key):
            return True
    return False


class TestHuntgroupEnforcement:
    """Lock the contract: a failing radgroupcheck MUST produce Access-Reject."""

    @pytest.mark.radius
    def test_matching_nas_returns_accept_with_reply_attrs(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 1 — matching NAS-IP + radgroupcheck → Access-Accept with reply attrs.

        GIVEN user juan.perez → group oficina-admin
              office-admin has radgroupcheck NAS-IP-Address == 192.168.1.10
              office-admin has radgroupreply Cisco-AVPair = "shell:priv-lvl=15"
        WHEN  Access-Request from NAS-IP-Address 192.168.1.10
        THEN  FreeRADIUS returns Access-Accept
              AND the reply contains Cisco-AVPair = "shell:priv-lvl=15"
        """
        del skip_if_no_radius  # explicit autouse-free skip semantics

        try:
            reply = _send_access_request(
                radius_client, USER_IN_CHECKED_GROUP, PASSWORD, NAS_MATCHING
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept (2) for matching NAS, got code {reply.code}"
        )
        assert _reply_contains_avpair_marker(reply, PRIV_LVL_15_MARKER), (
            f"Expected Cisco-AVPair = {PRIV_LVL_15_MARKER!r} in reply, "
            f"got keys={list(reply.keys())}"
        )

    @pytest.mark.radius
    def test_mismatching_nas_returns_reject(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 2 — non-matching NAS-IP + radgroupcheck → Access-Reject.

        GIVEN user juan.perez → group oficina-admin
              office-admin has radgroupcheck NAS-IP-Address == 192.168.1.10
        WHEN  Access-Request from NAS-IP-Address 192.168.1.50
        THEN  FreeRADIUS returns Access-Reject
              AND no Cisco-AVPair is present in the reply

        On the unfixed `radius/default.conf` (master, line 441 = `-sql`),
        FreeRADIUS strips the reply attributes but still returns
        Access-Accept — the bug from issue #92. This test is RED on
        master and GREEN after the config flip.
        """
        del skip_if_no_radius  # explicit autouse-free skip semantics

        try:
            reply = _send_access_request(
                radius_client, USER_IN_CHECKED_GROUP, PASSWORD, NAS_MISMATCHING
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessReject, (
            f"Expected Access-Reject (3) for mismatching NAS, got code {reply.code}. "
            "Huntgroup enforcement is broken — see GitHub issue #92."
        )
        assert not _reply_contains_avpair_marker(reply, PRIV_LVL_15_MARKER), (
            "Expected no Cisco-AVPair in Access-Reject reply, but found "
            f"{PRIV_LVL_15_MARKER!r}"
        )

    @pytest.mark.radius
    def test_group_without_check_returns_accept(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 3 — group with NO radgroupcheck rows → Access-Accept (regression).

        GIVEN user maria.lopez → group branch-read
              branch-read has NO radgroupcheck rows
              branch-read has radgroupreply Cisco-AVPair = "shell:priv-lvl=1"
        WHEN  Access-Request from NAS-IP-Address 192.168.1.50
        THEN  FreeRADIUS returns Access-Accept
              AND the reply contains Cisco-AVPair = "shell:priv-lvl=1"

        Regression guard: the config flip must NOT change behavior for groups
        that have no enforcement rules.
        """
        del skip_if_no_radius  # explicit autouse-free skip semantics

        try:
            reply = _send_access_request(
                radius_client, USER_IN_UNCHECKED_GROUP, PASSWORD, NAS_MISMATCHING
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept (2) for group without check rows, "
            f"got code {reply.code}"
        )
        assert _reply_contains_avpair_marker(reply, PRIV_LVL_1_MARKER), (
            f"Expected Cisco-AVPair = {PRIV_LVL_1_MARKER!r} in reply, "
            f"got keys={list(reply.keys())}"
        )

    @pytest.mark.radius
    def test_user_without_group_returns_accept(
        self, radius_client, skip_if_no_radius
    ):
        """Scenario 4 — user with NO radusergroup → Access-Accept (regression).

        GIVEN user carlos.ruiz has NO row in radusergroup
        WHEN  Access-Request from NAS-IP-Address 192.168.1.50
        THEN  FreeRADIUS returns Access-Accept
              AND behavior is unchanged from v1.3.4
              (no radgroupcheck was evaluated because no SQL-Group was resolved)

        Regression guard: the config flip must NOT change behavior for users
        with no group assignment.
        """
        del skip_if_no_radius  # explicit autouse-free skip semantics

        try:
            reply = _send_access_request(
                radius_client, USER_WITHOUT_GROUP, PASSWORD, NAS_MISMATCHING
            )
        except Timeout:
            pytest.skip("FreeRADIUS timed out — is FreeRADIUS running?")

        assert reply.code == packet.AccessAccept, (
            f"Expected Access-Accept (2) for user without radusergroup, "
            f"got code {reply.code}"
        )
