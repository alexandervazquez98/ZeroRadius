from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import RadGroupReply
from app.services import bandwidth_profiles
from app.schemas.access_policies import BandwidthProfilePayload


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def first(self):
        return self._value[0] if self._value else None

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_get_profile_returns_mapped_attributes():
    db = AsyncMock()
    rows = [
        RadGroupReply(groupname="MyProfile", attribute="Cambium-Canopy-HPDLCIR", op=":=", value="10000"),
        RadGroupReply(groupname="MyProfile", attribute="Cambium-Canopy-LPDLCIR", op=":=", value="20000"),
    ]
    db.execute.return_value = _ScalarResult(rows)

    profile = await bandwidth_profiles.get_profile(db, "MyProfile")
    assert profile is not None
    assert profile.name == "MyProfile"
    assert profile.groupname == "MyProfile"
    assert profile.downlink_high == "10000"
    assert profile.downlink_low == "20000"
    assert profile.uplink_high == "0"
    assert profile.uplink_low == "0"


@pytest.mark.asyncio
async def test_get_profile_returns_none_if_no_rows():
    db = AsyncMock()
    db.execute.return_value = _ScalarResult([])

    profile = await bandwidth_profiles.get_profile(db, "MissingProfile")
    assert profile is None


@pytest.mark.asyncio
async def test_upsert_profile_adds_attributes():
    db = AsyncMock()
    payload = BandwidthProfilePayload(
        name="New Profile",
        downlink_high="1000",
        uplink_high="500",
        downlink_low="2000",
        uplink_low="1000",
    )

    profile = await bandwidth_profiles.upsert_profile(db, payload)
    assert profile.groupname == "New Profile"
    assert profile.downlink_high == "1000"
    
    assert db.add.call_count == 4
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_profile_returns_true_if_exists():
    db = AsyncMock()
    rows = [RadGroupReply(groupname="MyProfile")]
    db.execute.return_value = _ScalarResult(rows)

    deleted = await bandwidth_profiles.delete_profile(db, "MyProfile")
    assert deleted is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_profile_returns_false_if_missing():
    db = AsyncMock()
    db.execute.return_value = _ScalarResult([])

    deleted = await bandwidth_profiles.delete_profile(db, "MissingProfile")
    assert deleted is False
    assert db.commit.call_count == 0
