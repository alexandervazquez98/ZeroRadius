"""
VSAGuardService — ISO 27001 A.5.15
Validates that Vendor-Specific Attributes (VSAs) are consistent with the NAS vendor
and detects high-privilege attribute assignments.
"""

from fastapi import HTTPException, status

# Map each NAS vendor to its expected VSA attribute name prefixes
VENDOR_ATTRIBUTE_MAP: dict[str, list[str]] = {
    "Cisco": ["Cisco-AVPair"],
    "Juniper": ["Juniper-Local-User-Name"],
    "Fortinet": ["Fortinet-Group-Name", "Fortinet-Vdom-Name"],
    "Huawei": ["Huawei-Exec-Privilege"],
    "Dahua": ["Dahua-Recording-Channel"],
}

# Patterns/values that indicate high-privilege assignments per vendor
HIGH_PRIVILEGE_ATTRS: dict[str, list[str]] = {
    "Cisco-AVPair": ["shell:priv-lvl=15", 'shell:roles="network-admin"'],
    "Juniper-Local-User-Name": ["superuser"],
    "Fortinet-Group-Name": ["super_admin_profile"],
    "Huawei-Exec-Privilege": ["15"],
}


def validate_vsa_vendor_consistency(nas_vendor: str, attributes: list[dict]) -> None:
    """
    Validate that all VSA attributes in the list are consistent with the declared NAS vendor.

    Standard RFC attributes (no vendor prefix) are always allowed.
    Vendor-specific attributes from a different vendor raise HTTP 422.

    Args:
        nas_vendor: The vendor name of the NAS (e.g., "Cisco", "Juniper")
        attributes: List of dicts with "name" and "value" keys

    Raises:
        HTTPException 422 if a VSA from a different vendor is found
    """
    # Build a set of attribute prefixes that belong to OTHER vendors
    foreign_prefixes: list[tuple[str, str]] = []
    for vendor, prefixes in VENDOR_ATTRIBUTE_MAP.items():
        if vendor.lower() != nas_vendor.lower():
            for prefix in prefixes:
                foreign_prefixes.append((vendor, prefix))

    for attr in attributes:
        attr_name = attr.get("name", "")
        for vendor, prefix in foreign_prefixes:
            if attr_name.startswith(prefix) or attr_name == prefix:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Attribute '{attr_name}' belongs to vendor '{vendor}' "
                        f"but NAS vendor is '{nas_vendor}'. "
                        "VSA vendor mismatch detected."
                    ),
                )


def check_high_privilege(attributes: list[dict]) -> bool:
    """
    Check if any of the provided attributes represent a high-privilege assignment.

    Returns True if a high-privilege attribute is found, False otherwise.
    """
    for attr in attributes:
        attr_name = attr.get("name", "")
        attr_value = str(attr.get("value", ""))

        if attr_name in HIGH_PRIVILEGE_ATTRS:
            high_priv_values = HIGH_PRIVILEGE_ATTRS[attr_name]
            for high_val in high_priv_values:
                if high_val in attr_value or attr_value == high_val:
                    return True
    return False
