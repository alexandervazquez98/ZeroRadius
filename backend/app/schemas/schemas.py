from pydantic import BaseModel, field_validator
from typing import Optional, List, Any
from datetime import datetime, date


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
    secret: str = "secret"
    description: Optional[str] = None


class NasOut(NasBase):
    id: int

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

    @field_validator("secret")
    @classmethod
    def secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                f"NAS secret must be at least 32 characters (got {len(v)}). "
                "Use a strong randomly-generated secret."
            )
        return v


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


# T23 — UserNasPrivilegeMap schemas
class UserNasPrivilegeMapCreate(BaseModel):
    username: str
    nas_ip: str
    nas_identifier: Optional[str] = None
    nas_vendor: Optional[str] = None
    radius_group: str
    privilege_level: Optional[str] = None
    justification: Optional[str] = None
    approved_by: Optional[str] = None
    review_date: Optional[date] = None
    is_active: int = 1


class UserNasPrivilegeMapBulkCreate(BaseModel):
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


class UserNasPrivilegeMapOut(UserNasPrivilegeMapCreate):
    id: int
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
