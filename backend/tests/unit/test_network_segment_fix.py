"""Regression tests for Issue #55: network-segments segment invariants."""

import pytest
import ipaddress
from pydantic import ValidationError

from app.schemas.schemas import (
    NetworkSegmentCreate,
    NetworkSegmentUpdate,
    UserNasPrivilegeMapCreate,
    UserNasPrivilegeMapBulkCreate,
)


class TestNetworkSegmentIPv4Only:
    """FIX #55: Only IPv4 is supported."""

    def test_ipv4_accepted_and_normalized(self):
        """IPv4 CIDR should be normalized to canonical form."""
        seg = NetworkSegmentCreate(name="test", cidr="10.0.0.5/24")
        assert seg.cidr == "10.0.0.0/24"

    def test_ipv4_canonical_unchanged(self):
        """Already canonical IPv4 should remain unchanged."""
        seg = NetworkSegmentCreate(name="test", cidr="10.0.0.0/24")
        assert seg.cidr == "10.0.0.0/24"

    def test_ipv4_host_bits_normalized(self):
        """Host bits should be normalized to network address."""
        seg = NetworkSegmentCreate(name="test", cidr="192.168.1.100/16")
        assert seg.cidr == "192.168.0.0/16"

    def test_ipv6_rejected(self):
        """IPv6 should be rejected with clear error."""
        with pytest.raises(ValidationError) as exc_info:
            NetworkSegmentCreate(name="test", cidr="2001:db8::/32")
        assert "IPv4" in str(exc_info.value)

    def test_invalid_cidr_rejected(self):
        """Invalid CIDR should be rejected."""
        with pytest.raises(ValidationError):
            NetworkSegmentCreate(name="test", cidr="invalid")


class TestNetworkSegmentUpdateIPv4Only:
    """Update endpoint should also enforce IPv4-only."""

    def test_update_ipv4_normalized(self):
        """Update should normalize IPv4."""
        seg = NetworkSegmentUpdate(cidr="10.0.0.5/24")
        assert seg.cidr == "10.0.0.0/24"

    def test_update_ipv6_rejected(self):
        """Update should reject IPv6."""
        with pytest.raises(ValidationError) as exc_info:
            NetworkSegmentUpdate(cidr="fe80::/64")
        assert "IPv4" in str(exc_info.value)

    def test_update_none_cidr_unchanged(self):
        """None CIDR should be allowed (no update)."""
        seg = NetworkSegmentUpdate(name="new-name")
        assert seg.cidr is None


class TestPrivilegeMapExceptionIPv4Only:
    """Exception IPs should also be IPv4-only."""

    def test_exception_ipv4_accepted(self):
        """IPv4 exception range should be accepted."""
        priv = UserNasPrivilegeMapCreate(
            username="testuser",
            segment_id=1,
            target_start_ip="10.0.0.10",
            target_end_ip="10.0.0.20",
            radius_group="group1",
        )
        assert priv.target_start_ip == "10.0.0.10"
        assert priv.target_end_ip == "10.0.0.20"

    def test_exception_ipv6_rejected(self):
        """IPv6 exception should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserNasPrivilegeMapCreate(
                username="testuser",
                segment_id=1,
                target_start_ip="fe80::1",
                target_end_ip="fe80::10",
                radius_group="group1",
            )
        assert "IPv4" in str(exc_info.value)

    def test_exception_mixed_rejected(self):
        """Mixed IPv4/IPv6 should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserNasPrivilegeMapCreate(
                username="testuser",
                segment_id=1,
                target_start_ip="10.0.0.10",
                target_end_ip="fe80::10",
                radius_group="group1",
            )
        assert "IPv4" in str(exc_info.value)


class TestPrivilegeMapNasIpIPv4Only:
    """nas_ip field should also be IPv4-only."""

    def test_nas_ip_ipv4_accepted(self):
        """IPv4 nas_ip should be accepted."""
        priv = UserNasPrivilegeMapCreate(
            username="testuser",
            nas_ip="10.0.0.5",
            radius_group="group1",
        )
        assert priv.nas_ip == "10.0.0.5"

    def test_nas_ip_ipv6_rejected(self):
        """IPv6 nas_ip should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserNasPrivilegeMapCreate(
                username="testuser",
                nas_ip="fe80::1",
                radius_group="group1",
            )
        assert "IPv4" in str(exc_info.value)


class TestBulkCreationIPv4Only:
    """Bulk creation should enforce IPv4-only."""

    def test_bulk_ipv4_accepted(self):
        """IPv4 bulk IPs should be accepted."""
        bulk = UserNasPrivilegeMapBulkCreate(
            username="testuser",
            nas_ips=["10.0.0.1", "10.0.0.2", "10.0.0.3"],
            radius_group="group1",
        )
        assert bulk.nas_ips == ["10.0.0.1", "10.0.0.2", "10.0.0.3"]

    def test_bulk_ipv6_rejected(self):
        """IPv6 in bulk should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserNasPrivilegeMapBulkCreate(
                username="testuser",
                nas_ips=["10.0.0.1", "2001:db8::1"],
                radius_group="group1",
            )
        assert "IPv4" in str(exc_info.value)

    def test_bulk_invalid_rejected(self):
        """Invalid IP in bulk should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            UserNasPrivilegeMapBulkCreate(
                username="testuser",
                nas_ips=["not-an-ip"],
                radius_group="group1",
            )
        assert "IPv4" in str(exc_info.value)
