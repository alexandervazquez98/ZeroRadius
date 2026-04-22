import ipaddress
import re
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


# cir-metrics-ui: CIR base schemas
_CIR_RATE_PATTERN = re.compile(r"^\d+$")


class CIRProfilePayload(BaseModel):
    name: str
    downlink_high: str
    uplink_high: str
    downlink_low: str
    uplink_low: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator(
        "downlink_high", "uplink_high", "downlink_low", "uplink_low", mode="before"
    )
    @classmethod
    def validate_rate(cls, v: str) -> str:
        value = str(v or "").strip()
        if not value:
            raise ValueError("rate value is required")
        if not _CIR_RATE_PATTERN.match(value):
            raise ValueError("rate must be numeric")
        return value


class CIRProfileOut(CIRProfilePayload):
    groupname: str
    model_config = ConfigDict(from_attributes=True)


class CIRResolutionTraceItem(BaseModel):
    step: str
    matched: bool
    detail: Optional[str] = None


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class RadGroupReplyBase(BaseModel):
    groupname: str
    attribute: str
    op: str = ":="
    value: str


class RadGroupReplyCreate(RadGroupReplyBase):
    pass


class RadGroupReplyOut(RadGroupReplyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class RadUserGroupBase(BaseModel):
    username: str
    groupname: str
    priority: int = 1


class RadUserGroupCreate(RadUserGroupBase):
    pass


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
    def require_nas_target(self):
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
                    raise ValueError(
                        "Exception IPs must be IPv4 only (IPv6 not supported)"
                    )
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


class UserNasPrivilegeMapOut(BaseModel):
    id: int
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_category_id: Optional[int] = None
    nas_category_name: Optional[str] = None
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None
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
    model_config = ConfigDict(from_attributes=True)


class CIRAssignmentPayload(UserNasPrivilegeMapCreate):
    @field_validator("radius_group")
    @classmethod
    def validate_radius_group(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("radius_group is required")
        if not value.startswith("cir_"):
            raise ValueError("radius_group must start with cir_")
        return value


class CIRPreviewRequest(BaseModel):
    username: str
    nas_ip: str
    calling_station_id: Optional[str] = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("username is required")
        return value

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v: str) -> str:
        try:
            ip = ipaddress.ip_address(v)
            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("nas_ip must be IPv4 only (IPv6 not supported)")
            return str(ip)
        except ValueError:
            raise ValueError("nas_ip must be a valid IPv4 address")


class CIRPreviewResponse(BaseModel):
    resolution_path: str
    mapping: Optional[UserNasPrivilegeMapOut] = None
    profile: Optional[CIRProfileOut] = None
    trace: List[CIRResolutionTraceItem]


# Session Schema
class SessionOut(BaseModel):
    radacctid: int
    username: str
    nasipaddress: str
    callingstationid: str
    framedipaddress: str
    acctstarttime: datetime
    session_time: Optional[int] = None
    input_octets: Optional[int] = None
    output_octets: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    nas_ip_address: Optional[str] = None
    nas_identifier: Optional[str] = None
    calling_station_id: Optional[str] = None
    called_station_id: Optional[str] = None
    reply_message: Optional[str] = None
    event_source: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class SIEMEvent(BaseModel):
    event_id: int
    timestamp_utc: datetime
    identity: dict
    action: str
    table_affected: str
    authorization_result: Optional[str] = None
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class NTPStatusResponse(BaseModel):
    synchronized: bool
    offset_ms: Optional[float] = None
    stratum: Optional[int] = None
    reference_server: Optional[str] = None
    last_sync: Optional[str] = None
    alert: bool


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


class NasCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    criticality: str = "standard"
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
    model_config = ConfigDict(from_attributes=True)


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
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError("cidr must be IPv4 only")
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
            if not isinstance(network, ipaddress.IPv4Network):
                raise ValueError("cidr must be IPv4 only")
            return f"{network.network_address}/{network.prefixlen}"
        except ValueError:
            raise ValueError("cidr must be a valid IPv4 network CIDR")


class NetworkSegmentOut(NetworkSegmentBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


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
            raise ValueError(f"NAS secret must be at least 32 characters (got {len(v)})")
        return v

    @field_validator("nasname")
    @classmethod
    def validate_nasname(cls, v: str) -> str:
        try:
            ipaddress.ip_address(v)
            return v
        except ValueError:
            pass
        try:
            ipaddress.ip_network(v, strict=False)
            return v
        except ValueError:
            pass
        hostname_re = re.compile(r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")
        if hostname_re.match(v):
            return v
        raise ValueError("nasname must be a valid IP, CIDR, or hostname")


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
    model_config = ConfigDict(from_attributes=True)


class UserNasPrivilegeMapBulkCreate(BaseModel):
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
                    raise ValueError("nas_ips must be IPv4 only")
            except ValueError:
                raise ValueError(f"invalid IP: {ip_str}")
        return v
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
    radius_group: str
    privilege_level: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None
    review_date: Optional[date] = None
    is_active: int = 1


class LoginAttemptOut(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    attempted_at: Optional[datetime] = None
    success: int
    model_config = ConfigDict(from_attributes=True)


class HardwareZoneBase(BaseModel):
    name: str
    description: Optional[str] = None


class HardwareZoneCreate(HardwareZoneBase):
    pass


class HardwareZoneOut(HardwareZoneBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class IAMRoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class IAMRoleCreate(IAMRoleBase):
    pass


class IAMRoleOut(IAMRoleBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PolicyMacroBase(BaseModel):
    name: str
    description: Optional[str] = None
    attributes_json: dict = {}


class PolicyMacroCreate(PolicyMacroBase):
    pass


class PolicyMacroOut(PolicyMacroBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class RoleZonePolicyBase(BaseModel):
    role_id: int
    zone_id: int
    policy_id: int


class RoleZonePolicyCreate(RoleZonePolicyBase):
    pass


class RoleZonePolicyOut(RoleZonePolicyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# T25 — Syslog Schemas
class SyslogEventOut(BaseModel):
    id: int
    timestamp: datetime
    facility: Optional[str] = None
    priority: Optional[str] = None
    device_ip: str
    hostname: Optional[str] = None
    tag: Optional[str] = None
    message: str
    model_config = ConfigDict(from_attributes=True)
