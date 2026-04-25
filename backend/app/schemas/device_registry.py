import re
import ipaddress
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

_MAC_ACCEPTED_FORMATS = (
    re.compile(r"^[0-9a-fA-F]{12}$"),
    re.compile(r"^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$"),
    re.compile(r"^(?:[0-9a-fA-F]{2}-){5}[0-9a-fA-F]{2}$"),
    re.compile(r"^(?:[0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}$"),
)


def _normalize_mac(value: str) -> str:
    if not any(p.fullmatch(value) for p in _MAC_ACCEPTED_FORMATS):
        raise ValueError(f"invalid MAC format: '{value}'")
    return re.sub(r"[:.\-]", "", value).lower()


class DeviceRegistryBase(BaseModel):
    mac: str
    name: Optional[str] = None
    category_id: Optional[int] = None
    nas_ip: Optional[str] = None
    description: Optional[str] = None
    is_active: int = 1

    @field_validator("mac")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        return _normalize_mac(v.strip())

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        try:
            ipaddress.ip_address(cleaned)
        except ValueError as exc:
            raise ValueError(f"invalid IP address: '{cleaned}'") from exc
        return cleaned


class DeviceRegistryCreate(DeviceRegistryBase):
    pass


class DeviceRegistryUpdate(BaseModel):
    name: Optional[str] = None
    category_id: Optional[int] = None
    nas_ip: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None

    @field_validator("nas_ip")
    @classmethod
    def validate_nas_ip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            return None
        try:
            ipaddress.ip_address(cleaned)
        except ValueError as exc:
            raise ValueError(f"invalid IP address: '{cleaned}'") from exc
        return cleaned


class DeviceRegistryOut(DeviceRegistryBase):
    id: int
    category_name: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class DeviceRegistryBulkCreate(BaseModel):
    devices: list[DeviceRegistryCreate]
    category_id: Optional[int] = None  # default category for all if not specified per device

    @field_validator("devices")
    @classmethod
    def validate_not_empty(cls, v):
        if not v:
            raise ValueError("devices list cannot be empty")
        return v


class DeviceRegistryBulkResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
