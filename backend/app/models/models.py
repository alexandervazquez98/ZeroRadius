import datetime
import hashlib
import ipaddress
import re
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Text,
    TIMESTAMP,
    JSON,
    UniqueConstraint,
    Index,
    ForeignKey,
    Enum,
    text,
    event,
)
from sqlalchemy.dialects.mysql import DATETIME as MySQLDATETIME
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.schema import FetchedValue
from typing import Optional
from app.db.session import Base
import datetime
import secrets


_MAC_ACCEPTED_FORMATS = (
    re.compile(r"^[0-9a-fA-F]{12}$"),
    re.compile(r"^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$"),
    re.compile(r"^(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}$"),
    re.compile(r"^(?:[0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$"),
)


def _normalize_mac(value: str) -> str:
    """Validate exact supported MAC formats, then normalize to 12 lowercase hex."""
    if not any(pattern.fullmatch(value) for pattern in _MAC_ACCEPTED_FORMATS):
        raise ValueError("invalid MAC address format (must be 12 hex chars)")
    return re.sub(r"[:.\-]", "", value).lower()


def _generate_secret() -> str:
    """Generate a random 48-character secret for NAS devices."""
    return secrets.token_urlsafe(36)


class RadCheck(Base):
    __tablename__ = "radcheck"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    attribute: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    op: Mapped[str] = mapped_column(String(2), nullable=False, default="==")
    value: Mapped[str] = mapped_column(String(253), nullable=False, default="")


class RadReply(Base):
    __tablename__ = "radreply"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    attribute: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    op: Mapped[str] = mapped_column(String(2), nullable=False, default="=")
    value: Mapped[str] = mapped_column(String(253), nullable=False, default="")


class RadUserGroup(Base):
    __tablename__ = "radusergroup"
    username: Mapped[str] = mapped_column(
        String(64), primary_key=True, nullable=False, default=""
    )
    groupname: Mapped[str] = mapped_column(
        String(64), primary_key=True, nullable=False, default=""
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class RadGroupCheck(Base):
    __tablename__ = "radgroupcheck"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    groupname: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    attribute: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    op: Mapped[str] = mapped_column(String(2), nullable=False, default="==")
    value: Mapped[str] = mapped_column(String(253), nullable=False, default="")


class RadGroupReply(Base):
    __tablename__ = "radgroupreply"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    groupname: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    attribute: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    op: Mapped[str] = mapped_column(String(2), nullable=False, default="=")
    value: Mapped[str] = mapped_column(String(253), nullable=False, default="")


class Nas(Base):
    __tablename__ = "nas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nasname: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    shortname: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(
        String(30), default="other", nullable=True
    )
    ports: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    secret: Mapped[str] = mapped_column(String(60), nullable=False, default="secret")
    server: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    community: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(
        String(200), default="RADIUS Client", nullable=True
    )
    # nas-categories feature: structured device classification
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nas_categories.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[Optional["NasCategory"]] = relationship(
        "NasCategory", back_populates="nases"
    )


class RadAcct(Base):
    __tablename__ = "radacct"
    radacctid: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    acctsessionid: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    acctuniqueid: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, default=""
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    groupname: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    realm: Mapped[Optional[str]] = mapped_column(String(64), default="", nullable=True)
    nasipaddress: Mapped[str] = mapped_column(
        String(15), nullable=False, default="", index=True
    )
    nasportid: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    nasporttype: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    acctstarttime: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, index=True, nullable=True
    )
    acctupdatetime: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    acctstoptime: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, index=True, nullable=True
    )
    acctinterval: Mapped[Optional[int]] = mapped_column(
        Integer, index=True, nullable=True
    )
    acctsessiontime: Mapped[Optional[int]] = mapped_column(
        Integer, index=True, nullable=True
    )
    acctauthentic: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    connectinfo_start: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    connectinfo_stop: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    acctinputoctets: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    acctoutputoctets: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    calledstationid: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    callingstationid: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )

    @validates("callingstationid")
    def validate_callingstationid(self, key, value):
        if value is None:
            return value
        return _normalize_mac(value)

    acctterminatecause: Mapped[str] = mapped_column(
        String(32), nullable=False, default=""
    )
    servicetype: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    framedprotocol: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    framedipaddress: Mapped[str] = mapped_column(
        String(15), nullable=False, default="", index=True
    )
    # T08 — extended accounting fields (ISO 27001 A.8.15)
    nasidentifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    privilege_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    vendor_reply_attrs: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class RadPostAuth(Base):
    __tablename__ = "radpostauth"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pass_: Mapped[str] = mapped_column(
        "pass", String(64), nullable=False, default=""
    )  # 'pass' is reserved keyword
    reply: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    authdate: Mapped[datetime.datetime] = mapped_column(
        MySQLDATETIME(fsp=6), server_default=func.now(), nullable=False
    )
    # T07 — enhanced traceability fields (ISO 27001 A.8.15, A.5.33)
    nas_ip_address: Mapped[str] = mapped_column(String(15), nullable=False, default="")
    nas_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nas_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calling_station_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    @validates("calling_station_id")
    def validate_calling_station_id(self, key, value):
        if value is None:
            return value
        return _normalize_mac(value)

    called_station_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reply_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="radius"
    )
    integrity_hash: Mapped[Optional[str]] = mapped_column(String(71), nullable=True)


class AppAuditLog(Base):
    __tablename__ = "app_audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user: Mapped[str] = mapped_column(String(255), nullable=False)
    target_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    table_affected: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP, server_default=func.now(), nullable=True
    )


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1)
    force_password_change: Mapped[int] = mapped_column(
        Integer, default=1
    )  # 1=True, 0=False
    # T03 — role column for RBAC (ISO 27001 A.5.15, A.5.18)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")


# T04 — LoginAttempt model for account lockout (ISO 27001 A.5.17)
class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    attempted_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("idx_username_time", "username", "attempted_at"),)


# T05 — RadiusReplyAudit model (ISO 27001 A.5.15, A.8.2, A.5.18)
class RadiusReplyAudit(Base):
    __tablename__ = "radius_reply_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    nas_ip: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    nas_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    radius_group: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reply_attributes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    privilege_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    event_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    admin_user: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    record_hash: Mapped[Optional[str]] = mapped_column(String(71), nullable=True)


# T06 — UserNasPrivilegeMap model (ISO 27001 A.5.15, A.8.2)
class AccessPolicyAssignment(Base):
    __tablename__ = "access_policy_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # T26 — target_key for absolute uniqueness (sha256 hash)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False)
    # nas-categories: nas_ip is nullable when using category-based targeting
    nas_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    calling_station_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nas_category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(
            "nas_categories.id",
            ondelete="SET NULL",
            name="fk_unpm_category",
        ),
        nullable=True,
    )
    category: Mapped[Optional["NasCategory"]] = relationship(
        "NasCategory", foreign_keys=[nas_category_id]
    )
    # network-segments-v1: targeting by network segment and IP ranges
    segment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey(
            "network_segments.id",
            ondelete="RESTRICT",
            name="fk_unpm_segment",
        ),
        nullable=True,
    )
    segment: Mapped[Optional["NetworkSegment"]] = relationship(
        "NetworkSegment", foreign_keys=[segment_id]
    )
    segment_target_key: Mapped[str] = mapped_column(
        String(128), nullable=False, default=""
    )
    target_start_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_end_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    nas_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nas_vendor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    radius_group: Mapped[str] = mapped_column(String(64), nullable=False)
    privilege_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    review_date: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        server_onupdate=FetchedValue(),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint("target_key", name="uq_unpm_target_key"),
    )

    @validates("calling_station_id")
    def validate_calling_station_id(self, key, value):
        if value is None:
            return value
        return _normalize_mac(value)

    def compute_target_key(self) -> str:
        """Deterministic sha256 hash for absolute uniqueness.
        Uses length-prefixed components to prevent delimiter injection attacks.
        Distinguishes None from empty values.
        """

        def safe(val):
            if val is None:
                return "4:None"
            s = str(val)
            return f"{len(s)}:{s}"

        components = [
            safe(self.username),
            safe(self.nas_ip),
            safe(self.calling_station_id),
            safe(self.nas_category_id),
            safe(self.segment_id),
            safe(self.target_start_ip),
            safe(self.target_end_ip),
        ]
        raw = "|".join(components)
        return hashlib.sha256(raw.encode()).hexdigest()


@event.listens_for(AccessPolicyAssignment, "before_insert")
def set_target_key_on_insert(mapper, connection, target: AccessPolicyAssignment):
    target.target_key = target.compute_target_key()


@event.listens_for(AccessPolicyAssignment, "before_update")
def set_target_key_on_update(mapper, connection, target: AccessPolicyAssignment):
    target.target_key = target.compute_target_key()


def _build_segment_target_key(
    segment_id: Optional[int],
    target_start_ip: Optional[str],
    target_end_ip: Optional[str],
) -> str:
    """Build logical key for segment rules. Matches compute_target_key logic."""

    def safe(val):
        if val is None:
            return "4:None"
        s = str(val)
        return f"{len(s)}:{s}"

    if segment_id is None:
        return ""

    if not target_start_ip and not target_end_ip:
        return "__base__"

    return f"{safe(target_start_ip)}|{safe(target_end_ip)}"


@event.listens_for(AccessPolicyAssignment, "before_insert")
@event.listens_for(AccessPolicyAssignment, "before_update")
def _sync_segment_target_key(mapper, connection, target):
    target.segment_target_key = _build_segment_target_key(
        target.segment_id,
        target.target_start_ip,
        target.target_end_ip,
    )


# --- Access Policies Domain Models ---


class NetworkSegment(Base):
    """Network Segments for access policy targeting."""

    __tablename__ = "network_segments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    cidr: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        server_onupdate=FetchedValue(),
        nullable=True,
    )


# nas-categories feature: structured NAS device classification
class NasCategory(Base):
    """Structured category for NAS devices (AP, SM, Camera, Switch, etc.).

    criticality:
        - critical:    Only privileged roles may access. Extra policy enforcement.
        - standard:    Normal network devices.
        - restricted:  Limited-access devices (read-only or no user access by default).
    """

    __tablename__ = "nas_categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    criticality: Mapped[str] = mapped_column(
        String(20), nullable=False, default="standard"
    )
    vendor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )

    nases: Mapped[list["Nas"]] = relationship("Nas", back_populates="category")
    devices: Mapped[list["DeviceRegistry"]] = relationship("DeviceRegistry", back_populates="category")


class DeviceRegistry(Base):
    """Known endpoint devices (SMs, CPEs) identified by MAC address.
    Assigned to a NAS category so RADIUS can resolve device-level policies
    without registering individual MACs in access_policy_assignments.
    """

    __tablename__ = "device_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("nas_categories.id", ondelete="SET NULL", name="fk_device_category"),
        nullable=True,
    )
    category: Mapped[Optional["NasCategory"]] = relationship("NasCategory", back_populates="devices")
    nas_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False),
        server_default=text("CURRENT_TIMESTAMP(6)"),
        server_onupdate=FetchedValue(),
        nullable=True,
    )

    @validates("mac")
    def normalize_mac(self, key, value):
        if value is None:
            return value
        return _normalize_mac(value)


# syslog-compliance: Phase 2 - SyslogEvent model with hash chain for integrity
class SyslogEvent(Base):
    __tablename__ = "syslog_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    received_at: Mapped[datetime.datetime] = mapped_column(
        MySQLDATETIME(fsp=6), server_default=func.now(), nullable=False
    )
    device_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    facility: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    severity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    program: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    previous_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("idx_syslog_device_ip", "device_ip"),
        Index("idx_syslog_received_at", "received_at"),
        Index("idx_syslog_severity", "severity"),
        Index("idx_syslog_facility", "facility"),
    )
