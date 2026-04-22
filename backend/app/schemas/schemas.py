from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime, date
import re
import ipaddress


# RadCheck Schemas
class RadCheckBase(BaseModel):
    username: str
    attribute: str
    op: str = ":="
    value: str


class RadCheckCreate(RadCheckBase):
    pass


class RadCheckUpdate(BaseModel):
    username: Optional[str] = None
    attribute: Optional[str] = None
    op: Optional[str] = None
    value: Optional[str] = None


class RadCheckOut(RadCheckBase):
    id: int

    class Config:
        from_attributes = True


# RadReply Schemas
class RadReplyBase(BaseModel):
    username: str
    attribute: str
    op: str = "="
    value: str


class RadReplyCreate(RadReplyBase):
    pass


class RadReplyOut(RadReplyBase):
    id: int

    class Config:
        from_attributes = True


# Group Schemas
class RadGroupCheckBase(BaseModel):
    groupname: str
    attribute: str
    op: str = ":="
    value: str


class RadGroupCheckCreate(RadGroupCheckBase):
    pass


class RadGroupCheckOut(RadGroupCheckBase):
    id: int

    class Config:
        from_attributes = True


class RadGroupReplyBase(BaseModel):
    groupname: str
    attribute: str
    op: str = ":="
    value: str


class RadGroupReplyCreate(RadGroupReplyBase):
    pass


class RadGroupReplyOut(RadGroupReplyBase):
    id: int

    class Config:
        from_attributes = True


class RadUserGroupBase(BaseModel):
    username: str
    groupname: str
    priority: int = 1


class RadUserGroupCreate(RadUserGroupBase):
    pass


# Session Schema
class SessionOut(BaseModel):
    radacctid: int
    username: str
    nasipaddress: str
    callingstationid: str  # MAC
    framedipaddress: str  # IP Assigned
    acctstarttime: datetime
    session_time: Optional[int] = None  # Calculated
    input_octets: Optional[int] = None
    output_octets: Optional[int] = None

    class Config:
        from_attributes = True


# Audit Log Schema
class AuditLogOut(BaseModel):
    id: int
    admin_user: str
    target_user: Optional[str] = None
    action: str
    table_affected: str
    timestamp: datetime
    old_value: Optional[str] = None
    new_value: Optional[str] = None

    class Config:
        from_attributes = True


# Auth Schemas
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class RadPostAuthOut(BaseModel):
    id: int
    username: str
    reply: str
    authdate: Optional[datetime] = None
    # T07 / T23 — NAS traceability fields
    nas_ip_address: Optional[str] = None
    nas_identifier: Optional[str] = None
    calling_station_id: Optional[str] = None
    called_station_id: Optional[str] = None
    reply_message: Optional[str] = None
    event_source: Optional[str] = None

    class Config:
        from_attributes = True


# Admin User Schemas
class AdminUserBase(BaseModel):
    username: str
    email: Optional[str] = None
    is_active: int = 1
    role: str = "admin"


class AdminUserCreate(AdminUserBase):
    password: str


class AdminUserUpdate(BaseModel):
    password: Optional[str] = None
    is_active: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None


class AdminUserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    is_active: int
    role: str
    force_password_change: int

    class Config:
        from_attributes = True


# T23 — SIEM event schema (REQ-BE-005)
class SIEMEvent(BaseModel):
    event_id: int
    timestamp_utc: datetime
    identity: dict  # {"admin_user": ..., "target_user": ...}
    action: str
    table_affected: str
    authorization_result: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


# T23 — NTP status response schema
class NTPStatusResponse(BaseModel):
    synchronized: bool
    offset_ms: Optional[float] = None
    stratum: Optional[int] = None
    reference_server: Optional[str] = None
    last_sync: Optional[str] = None
    alert: bool


# T24 — Container stats response schema
class ContainerStatsResponse(BaseModel):
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


class ContainerStatsListResponse(BaseModel):
    containers: list[ContainerStatsResponse]
    total: int
    running: int
    stopped: int


# T25 — System resources response schema
class SystemResourcesResponse(BaseModel):
    cpu_percent: float
    cpu_count: int
    memory_total_gb: float
    memory_used_gb: float
    memory_percent: float
    disk_total_gb: float
    disk_used_gb: float
    disk_percent: float
    network_interfaces: list[str]


# nas-categories: NasCategory schemas
class NasCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    criticality: str = "standard"  # critical | standard | restricted
    vendor: Optional[str] = None


class NasCategoryCreate(NasCategoryBase):
    @field_validator("criticality")
    @classmethod
    def validate_criticality(cls, v: str) -> str:
        valid = {"critical", "standard", "restricted"}
        if v not in valid:
            raise ValueError(f"criticality must be one of {valid}")
        return v


class NasCategoryOut(NasCategoryBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# network-segments-v1: NetworkSegment schemas
class NetworkSegmentBase(BaseModel):
    name: str
    cidr: str
    description: Optional[str] = None


class NetworkSegmentCreate(NetworkSegmentBase):
    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        try:
            network = ipaddress.ip_network(v, strict=False)
            # FIX #55: Only IPv4 is supported (RADIUS authorization is IPv4-only)
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError("cidr must be IPv4 only (IPv6 not supported)")
            # Normalize CIDR to canonical form: 10.0.0.5/24 -> 10.0.0.0/24
            return f"{network.network_address}/{network.prefixlen}"
        except ValueError:
            raise ValueError("cidr must be a valid IPv4 network CIDR")


class NetworkSegmentUpdate(BaseModel):
    name: Optional[str] = None
    cidr: Optional[str] = None
    description: Optional[str] = None

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        try:
            network = ipaddress.ip_network(v, strict=False)
            # FIX #55: Only IPv4 is supported (RADIUS authorization is IPv4-only)
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError("cidr must be IPv4 only (IPv6 not supported)")
            # Normalize CIDR to canonical form
            return f"{network.network_address}/{network.prefixlen}"
        except ValueError:
            raise ValueError("cidr must be a valid IPv4 network CIDR")


class NetworkSegmentOut(NetworkSegmentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# NAS validation schema with secret length enforcement (T17 / T23)
class NasCreate(BaseModel):
    nasname: str
    shortname: Optional[str] = None
    type: Optional[str] = "other"
    ports: Optional[int] = None
    secret: str = "secret"
    description: Optional[str] = None
    zone_id: Optional[int] = None
    category_id: Optional[int] = None

    @field_validator("secret")
    @classmethod
    def secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                f"NAS secret must be at least 32 characters (got {len(v)}). "
                "Use a strong randomly-generated secret."
            )
        return v

    @field_validator("nasname")
    @classmethod
    def validate_nasname(cls, v: str) -> str:
        # Try IP address
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            pass
        # Try CIDR
        try:
            ipaddress.ip_network(v, strict=False)
            return v
        except ValueError:
            pass
        # Try hostname RFC-1123
        hostname_re = re.compile(
            r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$"
        )
        if hostname_re.match(v):
            return v
        raise ValueError(
            "nasname must be a valid IP address, CIDR, or RFC-1123 hostname"
        )


class NasOut(BaseModel):
    nasname: str
    shortname: Optional[str] = None
    type: Optional[str] = "other"
    ports: Optional[int] = None
    secret: str
    description: Optional[str] = None
    zone_id: Optional[int] = None
    category_id: Optional[int] = None
    id: int
    category_name: Optional[str] = None

    class Config:
        from_attributes = True


# T23 — UserNasPrivilegeMap schemas
class UserNasPrivilegeMapCreate(BaseModel):
    username: str
    nas_ip: Optional[str] = None  # IP-based targeting

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v):
        if v is None:
            return v
        try:
            ip = ipaddress.ip_address(v)
            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("nas_ip must be IPv4 only (IPv6 not supported)")
            return str(ip)
        except ValueError:
            raise ValueError("nas_ip must be a valid IPv4 address")

    calling_station_id: Optional[str] = None  # MAC-based targeting

    @field_validator("calling_station_id")
    @classmethod
    def validate_mac(cls, v):
        if v is None:
            return v
        # Support various delimiters: AA:BB, AA-BB, AA.BB.CC, AABB, etc.
        clean = re.sub(r"[:.\-]", "", v).lower()
        if not re.match(r"^[0-9a-f]{12}$", clean):
            raise ValueError(
                "calling_station_id must be a valid MAC address (12 hex chars)"
            )
        return clean

    nas_category_id: Optional[int] = None  # Category-based targeting
    segment_id: Optional[int] = None  # network-segments-v1: Segment targeting
    target_start_ip: Optional[str] = None  # network-segments-v1: Exception start
    target_end_ip: Optional[str] = None  # network-segments-v1: Exception end
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
    radius_group: str
    privilege_level: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None
    review_date: Optional[date] = None
    is_active: int = 1

    @model_validator(mode="after")
    def require_nas_target(self) -> "UserNasPrivilegeMapCreate":
        """Exactly one targeting mode (IP, Category, Segment, or MAC) must be provided."""
        has_ip = self.nas_ip is not None and self.nas_ip.strip() != ""
        has_mac = (
            self.calling_station_id is not None
            and self.calling_station_id.strip() != ""
        )
        has_cat = self.nas_category_id is not None
        has_seg = self.segment_id is not None

        # Determine if this is a range exception (Segment + IPs)
        is_range_exception = has_seg and (
            (self.target_start_ip and self.target_start_ip.strip() != "")
            or (self.target_end_ip and self.target_end_ip.strip() != "")
        )

        # Ensure we don't mix Category with anything else
        if has_cat and (has_ip or has_mac or has_seg):
            raise ValueError("nas_category_id cannot be combined with other targeting methods")

        # Ensure we don't mix Segment (base or exception) with IP or MAC
        if has_seg and (has_ip or has_mac):
             raise ValueError("Network Segment targeting cannot be combined with NAS IP or MAC")

        # Basic targeting exclusivity (one primary method)
        # Exception: MAC+IP is a specific supported combination (higher specificity)
        if not (has_ip and has_mac):
            provided_count = sum([has_ip, has_mac, has_cat, has_seg])
            if provided_count == 0:
                raise ValueError(
                    "Either nas_ip, calling_station_id, nas_category_id, or segment_id must be provided"
                )
            if provided_count > 1 and not is_range_exception:
                raise ValueError(
                    "Only one targeting method allowed (except MAC+IP or Segment Exception)"
                )

        if has_seg:
            has_start = (
                self.target_start_ip is not None and self.target_start_ip.strip() != ""
            )
            has_end = (
                self.target_end_ip is not None and self.target_end_ip.strip() != ""
            )

            if has_start != has_end:
                raise ValueError(
                    "Both target_start_ip and target_end_ip must be provided for a range exception, or neither for a base rule"
                )

            if has_start and has_end:
                try:
                    start_ip = ipaddress.ip_address(self.target_start_ip)
                    end_ip = ipaddress.ip_address(self.target_end_ip)
                except ValueError:
                    # FIX #55: Provide clear error for IPv6 or invalid format
                    raise ValueError(
                        "Exception IPs must be IPv4 only (IPv6 not supported)"
                    )
                # FIX #55: Only IPv4 is supported (RADIUS authorization is IPv4-only)
                if not isinstance(start_ip, ipaddress.IPv4Address):
                    raise ValueError(
                        "Exception IPs must be IPv4 only (IPv6 not supported)"
                    )
                if not isinstance(end_ip, ipaddress.IPv4Address):
                    raise ValueError(
                        "Exception IPs must be IPv4 only (IPv6 not supported)"
                    )
                if start_ip > end_ip:
                    raise ValueError(
                        "target_start_ip cannot be greater than target_end_ip"
                    )

        return self


class UserNasPrivilegeMapBulkCreate(BaseModel):
    """Bulk IP-based creation. For category-based entries use UserNasPrivilegeMapCreate."""

    username: str
    nas_ips: List[str]

    @field_validator("nas_ips")
    @classmethod
    def validate_nas_ips(cls, v):
        if not v:
            return v
        for ip_str in v:
            try:
                ip = ipaddress.ip_address(ip_str)
                if not isinstance(ip, ipaddress.IPv4Address):
                    raise ValueError("nas_ips must be IPv4 only (IPv6 not supported)")
            except ValueError:
                raise ValueError("nas_ips must be valid IPv4 addresses: " + ip_str + " is invalid")
        return v
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
    radius_group: str
    privilege_level: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None
    review_date: Optional[date] = None
    is_active: int = 1


class UserNasPrivilegeMapOut(BaseModel):
    id: int
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_category_id: Optional[int] = None
    nas_category_name: Optional[str] = None  # resolved from relationship in router
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None  # resolved from relationship in router
    target_start_ip: Optional[str] = None
    target_end_ip: Optional[str] = None
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
    radius_group: str
    privilege_level: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None
    review_date: Optional[date] = None
    is_active: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    days_until_review: Optional[int] = None

    class Config:
        from_attributes = True


# T23 — LoginAttempt output schema
class LoginAttemptOut(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    attempted_at: Optional[datetime] = None
    success: int

    class Config:
        from_attributes = True


# --- IAM & NAC RBAC Schemas ---


class HardwareZoneBase(BaseModel):
    name: str
    description: Optional[str] = None


class HardwareZoneCreate(HardwareZoneBase):
    pass


class HardwareZoneOut(HardwareZoneBase):
    id: int

    class Config:
        from_attributes = True


class IAMRoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class IAMRoleCreate(IAMRoleBase):
    pass


class IAMRoleOut(IAMRoleBase):
    id: int

    class Config:
        from_attributes = True


class PolicyMacroBase(BaseModel):
    name: str
    description: Optional[str] = None
    attributes_json: dict = {}


class PolicyMacroCreate(PolicyMacroBase):
    pass


class PolicyMacroOut(PolicyMacroBase):
    id: int

    class Config:
        from_attributes = True


class RoleZonePolicyBase(BaseModel):
    role_id: int
    zone_id: int
    policy_id: int


class RoleZonePolicyCreate(RoleZonePolicyBase):
    pass


class RoleZonePolicyOut(RoleZonePolicyBase):
    id: int

    class Config:
        from_attributes = True
