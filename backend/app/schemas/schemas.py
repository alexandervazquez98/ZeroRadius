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
    category_name: Optional[str] = None  # populated by router from relationship

    class Config:
        from_attributes = True


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


# T23 — UserNasPrivilegeMap schemas
class UserNasPrivilegeMapCreate(BaseModel):
    username: str
    nas_ip: Optional[str] = None  # IP-based targeting
    nas_category_id: Optional[int] = None  # Category-based targeting
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
        """Exactly one of nas_ip or nas_category_id must be provided."""
        has_ip = self.nas_ip is not None and self.nas_ip.strip() != ""
        has_cat = self.nas_category_id is not None
        if not has_ip and not has_cat:
            raise ValueError("Either nas_ip or nas_category_id must be provided")
        if has_ip and has_cat:
            raise ValueError("Provide either nas_ip or nas_category_id, not both")
        return self


class UserNasPrivilegeMapBulkCreate(BaseModel):
    """Bulk IP-based creation. For category-based entries use UserNasPrivilegeMapCreate."""

    username: str
    nas_ips: List[str]
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
    nas_category_id: Optional[int] = None
    nas_category_name: Optional[str] = None  # resolved from relationship in router
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
