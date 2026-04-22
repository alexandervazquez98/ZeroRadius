import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.models.models import NetworkSegment, UserNasPrivilegeMap


@pytest.mark.asyncio
async def test_regression_sqlite_foreign_keys_are_enforced(test_db):
    with pytest.raises(IntegrityError):
        await test_db.execute(
            text(
                """
                INSERT INTO user_nas_privilege_map (
                    username,
                    segment_id,
                    radius_group,
                    is_active
                ) VALUES (
                    'fk-user',
                    999999,
                    'group1',
                    1
                )
                """
            )
        )
        await test_db.commit()

    await test_db.rollback()


@pytest.mark.asyncio
async def test_regression_duplicate_base_segment_mapping_rejected_at_db_layer(test_db):
    segment = NetworkSegment(name="sqlite-base-segment", cidr="10.210.0.0/16")
    test_db.add(segment)
    await test_db.commit()
    await test_db.refresh(segment)

    first = UserNasPrivilegeMap(
        username="sqlite-dup-base",
        segment_id=segment.id,
        radius_group="group1",
        is_active=1,
    )
    second = UserNasPrivilegeMap(
        username="sqlite-dup-base",
        segment_id=segment.id,
        radius_group="group2",
        is_active=1,
    )

    test_db.add(first)
    await test_db.commit()

    test_db.add(second)
    with pytest.raises(IntegrityError):
        await test_db.commit()

    await test_db.rollback()
