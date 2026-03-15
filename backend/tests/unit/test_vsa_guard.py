"""
T39 — Unit tests for VSAGuardService.

Tests cover:
- Cisco attrs on Cisco NAS → OK
- Juniper attrs on Juniper NAS → OK
- Cisco attr on Juniper NAS → 422
- Fortinet attr on Cisco NAS → 422
- Standard RFC attrs always pass regardless of vendor
- Unknown vendor with standard attrs passes
- High-privilege checks: priv-lvl=15, superuser, super_admin_profile, Huawei 15
- Low-privilege attrs → not high priv
- Empty attrs → not high priv
"""

import pytest
from fastapi import HTTPException

from app.services.vsa_guard import validate_vsa_vendor_consistency, check_high_privilege


class TestVSAVendorConsistency:
    def test_cisco_attr_on_cisco_nas_passes(self):
        """Cisco-AVPair on a Cisco NAS is valid."""
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"}]
        # Should not raise
        validate_vsa_vendor_consistency("Cisco", attrs)

    def test_juniper_attr_on_juniper_nas_passes(self):
        """Juniper-Local-User-Name on a Juniper NAS is valid."""
        attrs = [{"name": "Juniper-Local-User-Name", "value": "readonly-user"}]
        validate_vsa_vendor_consistency("Juniper", attrs)

    def test_cisco_attr_on_juniper_nas_raises_422(self):
        """Cisco-AVPair on a Juniper NAS raises HTTP 422."""
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]
        with pytest.raises(HTTPException) as exc:
            validate_vsa_vendor_consistency("Juniper", attrs)
        assert exc.value.status_code == 422
        assert "Cisco-AVPair" in exc.value.detail
        assert "Juniper" in exc.value.detail

    def test_fortinet_attr_on_cisco_nas_raises_422(self):
        """Fortinet-Group-Name on a Cisco NAS raises HTTP 422."""
        attrs = [{"name": "Fortinet-Group-Name", "value": "super_admin_profile"}]
        with pytest.raises(HTTPException) as exc:
            validate_vsa_vendor_consistency("Cisco", attrs)
        assert exc.value.status_code == 422

    def test_standard_attr_passes_any_vendor(self):
        """Standard RFC attributes (Service-Type, etc.) are valid on any vendor."""
        attrs = [{"name": "Service-Type", "value": "NAS-Prompt-User"}]
        validate_vsa_vendor_consistency("Cisco", attrs)
        validate_vsa_vendor_consistency("Juniper", attrs)
        validate_vsa_vendor_consistency("Fortinet", attrs)

    def test_unknown_vendor_with_standard_attrs_passes(self):
        """Unknown vendor with non-VSA attributes is valid."""
        attrs = [{"name": "Session-Timeout", "value": "3600"}]
        validate_vsa_vendor_consistency("Generic", attrs)

    def test_huawei_attr_on_cisco_nas_raises_422(self):
        """Huawei-Exec-Privilege on a Cisco NAS raises HTTP 422."""
        attrs = [{"name": "Huawei-Exec-Privilege", "value": "15"}]
        with pytest.raises(HTTPException) as exc:
            validate_vsa_vendor_consistency("Cisco", attrs)
        assert exc.value.status_code == 422

    def test_empty_attributes_passes(self):
        """Empty attribute list is always valid."""
        validate_vsa_vendor_consistency("Cisco", [])

    def test_mixed_standard_and_vendor_attrs_passes_when_consistent(self):
        """Standard + matching vendor attrs passes without raising."""
        attrs = [
            {"name": "Service-Type", "value": "NAS-Prompt-User"},
            {"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"},
        ]
        validate_vsa_vendor_consistency("Cisco", attrs)


class TestHighPrivilegeCheck:
    def test_cisco_priv15_is_high_privilege(self):
        """Cisco-AVPair with shell:priv-lvl=15 is high privilege."""
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=15"}]
        assert check_high_privilege(attrs) is True

    def test_cisco_priv1_is_not_high_privilege(self):
        """Cisco-AVPair with shell:priv-lvl=1 is NOT high privilege."""
        attrs = [{"name": "Cisco-AVPair", "value": "shell:priv-lvl=1"}]
        assert check_high_privilege(attrs) is False

    def test_juniper_superuser_is_high_privilege(self):
        """Juniper-Local-User-Name with value 'superuser' is high privilege."""
        attrs = [{"name": "Juniper-Local-User-Name", "value": "superuser"}]
        assert check_high_privilege(attrs) is True

    def test_fortinet_super_admin_is_high_privilege(self):
        """Fortinet-Group-Name with value 'super_admin_profile' is high privilege."""
        attrs = [{"name": "Fortinet-Group-Name", "value": "super_admin_profile"}]
        assert check_high_privilege(attrs) is True

    def test_huawei_priv15_is_high_privilege(self):
        """Huawei-Exec-Privilege with value '15' is high privilege."""
        attrs = [{"name": "Huawei-Exec-Privilege", "value": "15"}]
        assert check_high_privilege(attrs) is True

    def test_empty_attrs_is_not_high_privilege(self):
        """Empty attribute list is never high privilege."""
        assert check_high_privilege([]) is False

    def test_standard_attrs_not_high_privilege(self):
        """Standard RFC attributes (no VSA) are not high privilege."""
        attrs = [
            {"name": "Service-Type", "value": "NAS-Prompt-User"},
            {"name": "Session-Timeout", "value": "3600"},
        ]
        assert check_high_privilege(attrs) is False

    def test_cisco_network_admin_is_high_privilege(self):
        """Cisco-AVPair with shell:roles=network-admin is high privilege."""
        attrs = [{"name": "Cisco-AVPair", "value": 'shell:roles="network-admin"'}]
        assert check_high_privilege(attrs) is True
