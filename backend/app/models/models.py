from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    TIMESTAMP,
    JSON,
    UniqueConstraint,
    Index,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import Optional
from app.db.session import Base
import datetime


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
    zone_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("hardware_zones.id", ondelete="SET NULL"), nullable=True
    )
    zone: Mapped[Optional["HardwareZone"]] = relationship("HardwareZone", back_populates="nases")
    # nas-categories feature: structured device classification
    category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nas_categories.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[Optional["NasCategory"]] = relationship("NasCategory", back_populates="nases")


class RadAcct(Base):
    __tablename__ = "radacct"
    radacctid: Mapped[int] = mapped_column(Integer, primary_key=True)
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
    acctinputoctets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    acctoutputoctets: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calledstationid: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    callingstationid: Mapped[str] = mapped_column(
        String(50), nullable=False, default=""
    )
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
    authdate: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )
    # T07 — enhanced traceability fields (ISO 27001 A.8.15, A.5.33)
    nas_ip_address: Mapped[Optional[str]] = mapped_column(String(15), nullable=True)
    nas_identifier: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    nas_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    calling_station_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    called_station_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reply_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_source: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="radius"
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
class UserNasPrivilegeMap(Base):
    __tablename__ = "user_nas_privilege_map"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    # nas-categories: nas_ip is nullable when using category-based targeting
    nas_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nas_category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("nas_categories.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[Optional["NasCategory"]] = relationship("NasCategory", foreign_keys=[nas_category_id])
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
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("username", "nas_ip", name="uq_user_nas_ip"),
        UniqueConstraint("username", "nas_category_id", name="uq_user_nas_cat"),
    )


# --- IAM & NAC RBAC Models ---

class HardwareZone(Base):
    __tablename__ = "hardware_zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    nases: Mapped[list["Nas"]] = relationship("Nas", back_populates="zone")


class IAM_Role(Base):
    __tablename__ = "iam_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PolicyMacro(Base):
    __tablename__ = "policy_macros"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attributes_json: Mapped[dict] = mapped_column(JSON, default={})


class RoleZonePolicy(Base):
    __tablename__ = "role_zone_policies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("iam_roles.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[int] = mapped_column(Integer, ForeignKey("hardware_zones.id", ondelete="CASCADE"), nullable=False)
    policy_id: Mapped[int] = mapped_column(Integer, ForeignKey("policy_macros.id", ondelete="CASCADE"), nullable=False)
    
    role: Mapped["IAM_Role"] = relationship("IAM_Role")
    zone: Mapped["HardwareZone"] = relationship("HardwareZone")
    policy: Mapped["PolicyMacro"] = relationship("PolicyMacro")
    
    __table_args__ = (UniqueConstraint("role_id", "zone_id", name="uq_role_zone_policy"),)


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
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    criticality: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")
    vendor: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True
    )

    nases: Mapped[list["Nas"]] = relationship("Nas", back_populates="category")
