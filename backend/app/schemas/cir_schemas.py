from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel, field_validator
from .schemas import UserNasPrivilegeMapCreate, UserNasPrivilegeMapOut

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

class CIRResolutionTraceItem(BaseModel):
    step: str
    matched: bool
    detail: Optional[str] = None

class CIRPreviewResponse(BaseModel):
    resolution_path: str
    mapping: Optional[UserNasPrivilegeMapOut] = None
    profile: Optional[CIRProfileOut] = None
    trace: list[CIRResolutionTraceItem]
