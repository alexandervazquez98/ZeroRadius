from pydantic import BaseModel, field_validator, model_validator, ConfigDict
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


# NAS Schemas
class NasBase(BaseModel):
    nasname: str
    shortname: Optional[str] = None
    type: Optional[str] = "other"
    ports: Optional[int] = None
    secret: str
    description: Optional[str] = None
    zone_id: Optional[int] = None
    category_id: Optional[int] = None

    @field_validator("secret")
    @classmethod
    def secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("NAS secret must be at least 32 characters")
        return v


class NasOut(NasBase):
    id: int
    category_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


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


# NAS validation schema with secret length enforcement
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


class UserNasPrivilegeMapCreate(BaseModel):
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_category_id: Optional[int] = None
    segment_id: Optional[int] = None
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

    @model_validator(mode="after")
    def require_nas_target(self):
        has_ip = self.nas_ip is not None and self.nas_ip.strip() != ""
        has_mac = self.calling_station_id is not None and self.calling_station_id.strip() != ""
        has_cat = self.nas_category_id is not None
        has_seg = self.segment_id is not None

        if not (has_ip and has_mac):
            provided = sum([has_ip, has_mac, has_cat, has_seg])
            if provided == 0:
                raise ValueError("targeting method required")
        return self


class UserNasPrivilegeMapBulkCreate(BaseModel):
    username: str
    nas_ips: List[str]
    radius_group: str
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
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


class LoginAttemptOut(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    attempted_at: Optional[datetime] = None
    success: int
    model_config = ConfigDict(from_attributes=True)
