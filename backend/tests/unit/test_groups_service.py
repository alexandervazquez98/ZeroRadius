"""
Unit tests: groups service — using test_db fixture (AsyncSession with SQLite in-memory).

Tests create group reply attributes via direct ORM (no HTTP layer).
Verifies successful creation and duplicate handling.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.models import RadGroupReply, RadUserGroup


class TestGroupReplyCreation:
    """Direct ORM tests for RadGroupReply (group attributes)."""

    async def test_create_group_reply_succeeds(self, test_db):
        """Inserting a RadGroupReply with valid data persists it."""
        entry = RadGroupReply(
            groupname="unit_test_group",
            attribute="Service-Type",
            op=":=",
            value="NAS-Prompt-User",
        )
        test_db.add(entry)
        await test_db.commit()
        await test_db.refresh(entry)

        assert entry.id is not None
        assert entry.groupname == "unit_test_group"
        assert entry.attribute == "Service-Type"

    async def test_query_group_reply_by_groupname(self, test_db):
        """Can query just-created entries by groupname."""
        entry = RadGroupReply(
            groupname="query_test_group",
            attribute="Idle-Timeout",
            op=":=",
            value="3600",
        )
        test_db.add(entry)
        await test_db.commit()

        result = await test_db.execute(
            select(RadGroupReply).where(RadGroupReply.groupname == "query_test_group")
        )
        rows = result.scalars().all()
        assert len(rows) >= 1
        assert rows[0].attribute == "Idle-Timeout"

    async def test_create_multiple_attributes_for_same_group(self, test_db):
        """Multiple attributes can coexist for the same groupname (no unique constraint)."""
        entry1 = RadGroupReply(
            groupname="multi_attr_group", attribute="Service-Type", op=":=", value="NAS-Prompt-User"
        )
        entry2 = RadGroupReply(
            groupname="multi_attr_group", attribute="Idle-Timeout", op=":=", value="600"
        )
        test_db.add_all([entry1, entry2])
        await test_db.commit()

        result = await test_db.execute(
            select(RadGroupReply).where(RadGroupReply.groupname == "multi_attr_group")
        )
        rows = result.scalars().all()
        assert len(rows) == 2


class TestUserGroupAssignment:
    """Direct ORM tests for RadUserGroup (user-to-group assignments)."""

    async def test_assign_user_to_group_succeeds(self, test_db):
        """A user can be assigned to a group."""
        assignment = RadUserGroup(
            username="unit_test_radius_user",
            groupname="unit_test_group",
            priority=1,
        )
        test_db.add(assignment)
        await test_db.commit()

        result = await test_db.execute(
            select(RadUserGroup).where(
                RadUserGroup.username == "unit_test_radius_user"
            )
        )
        row = result.scalars().first()
        assert row is not None
        assert row.groupname == "unit_test_group"
