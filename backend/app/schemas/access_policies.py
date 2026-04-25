import ipaddress
import re
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


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


_RATE_PATTERN = re.compile(r"^\d+$")


class BandwidthProfilePayload(BaseModel):
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

    @field_validator("downlink_high", "uplink_high", "downlink_low", "uplink_low", mode="before")
    @classmethod
    def validate_rate(cls, v: str) -> str:
        value = str(v or "").strip()
        if not value:
            raise ValueError("rate value is required")
        if not _RATE_PATTERN.match(value):
            raise ValueError("rate must be numeric")
        return value


class BandwidthProfileOut(BandwidthProfilePayload):
    groupname: str
    model_config = ConfigDict(from_attributes=True)


class AccessPolicyResolutionTraceItem(BaseModel):
    step: str
    matched: bool
    detail: Optional[str] = None


class AccessPolicyAssignmentCreate(BaseModel):
    username: str
    nas_ip: Optional[str] = None

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v):
        if v is None:
            return v
        try:
            ip = ipaddress.ip_address(v)
            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("nas_ip must be IPv4 only")
            return str(ip)
        except ValueError:
            raise ValueError("nas_ip must be a valid IPv4 address")

    calling_station_id: Optional[str] = None

    @field_validator("calling_station_id")
    @classmethod
    def validate_mac(cls, v):
        if v is None:
            return v
        return _normalize_mac(v)

    nas_category_id: Optional[int] = None
    segment_id: Optional[int] = None
    cir_id: Optional[int] = None
    target_start_ip: Optional[str] = None
    target_end_ip: Optional[str] = None

    @field_validator("target_start_ip", "target_end_ip")
    @classmethod
    def validate_range_ip(cls, v):
        if v is None or v.strip() == "":
            return v
        try:
            ip = ipaddress.ip_address(v)
            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("Exception IPs must be IPv4 only")
            return str(ip)
        except ValueError:
            raise ValueError("Exception IPs must be valid IPv4 addresses")

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
        has_ip = bool(self.nas_ip and self.nas_ip.strip())
        has_mac = bool(self.calling_station_id and self.calling_station_id.strip())
        has_cat = self.nas_category_id is not None
        has_seg = self.segment_id is not None
        has_cir = self.cir_id is not None

        is_range_exception = has_seg and (
            bool(self.target_start_ip and self.target_start_ip.strip())
            or bool(self.target_end_ip and self.target_end_ip.strip())
        )

        # 1. IP + MAC is high-specificity — no other targeting method allowed
        #    EXCEPT: CIR can override IP+MAC targeting (CIR takes precedence)
        if has_ip and has_mac:
            if has_cir:
                return self  # CIR overrides IP+MAC combination
            if has_cat or has_seg:
                raise ValueError("IP+MAC targeting cannot be combined with Category or Segment")
            return self

        # 2. Range Exception (Segment + IP range) — CIR can override segment
        if is_range_exception:
            if has_cat or has_ip or has_mac:
                raise ValueError("Network Segment range exceptions cannot be combined with other targeting methods")
            return self

        # 3. CIR assignments can optionally carry nas_ip and/or calling_station_id
        #    as routing context metadata, but CIR is the sole targeting method
        if has_cir:
            return self

        # 4. Segment assignments (without exception range) can have nas_ip for routing
        if has_seg:
            if has_mac:
                raise ValueError("Segment targeting cannot be combined with MAC")
            return self

        # 5. Otherwise, strictly ONE targeting method
        provided = sum([has_ip, has_mac, has_cat, has_seg, has_cir])
        if provided == 0:
            raise ValueError("targeting method required")
        if provided > 1:
            raise ValueError("exactly one targeting method required")

        return self


class AccessPolicyAssignmentOut(BaseModel):
    id: int
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_category_id: Optional[int] = None
    nas_category_name: Optional[str] = None
    segment_id: Optional[int] = None
    segment_name: Optional[str] = None
    cir_id: Optional[int] = None
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


class AccessPolicyAssignmentBulkCreate(BaseModel):
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

    @field_validator("nas_ips")
    @classmethod
    def validate_nas_ips_ipv4_only(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("nas_ips must contain at least one IPv4 address")

        normalized: List[str] = []
        for ip_raw in v:
            ip_candidate = ip_raw.strip()
            try:
                ip = ipaddress.ip_address(ip_candidate)
            except ValueError:
                raise ValueError("nas_ips entries must be valid IPv4 addresses")

            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("nas_ips entries must be IPv4 only")

            normalized.append(str(ip))

        return normalized


class AccessPolicyPreviewRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        value = (v or "").strip()
        if not value:
            raise ValueError("username is required")
        return value

    nas_ip: str

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v: str) -> str:
        try:
            ip = ipaddress.ip_address(v)
            if not isinstance(ip, ipaddress.IPv4Address):
                raise ValueError("nas_ip must be IPv4 only")
            return str(ip)
        except ValueError:
            raise ValueError("nas_ip must be a valid IPv4 address")

    calling_station_id: Optional[str] = None

    @field_validator("calling_station_id")
    @classmethod
    def validate_mac(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return _normalize_mac(v)


class AccessPolicyPreviewResponse(BaseModel):
    resolution_path: str
    mapping: Optional[AccessPolicyAssignmentOut] = None
    profile: Optional[BandwidthProfileOut] = None
    trace: List[AccessPolicyResolutionTraceItem]


class CategoryReassignPayload(BaseModel):
    target_category_id: int
