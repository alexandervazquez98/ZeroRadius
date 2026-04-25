"""Rename user_nas_privilege_map to access_policy_assignments

Revision ID: c0123d4
Revises: b92d5e1
Create Date: 2026-04-23 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'c0123d4'
down_revision: Union[str, None] = 'b92d5e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename table
    op.rename_table('user_nas_privilege_map', 'access_policy_assignments')

    conn = op.get_bind()
    # Strip cir_ from radgroupreply
    conn.execute(text("UPDATE radgroupreply SET groupname = SUBSTRING(groupname, 5) WHERE groupname LIKE 'cir_%'"))
    
    # Strip cir_ from access_policy_assignments
    conn.execute(text("UPDATE access_policy_assignments SET radius_group = SUBSTRING(radius_group, 5) WHERE radius_group LIKE 'cir_%'"))


def downgrade() -> None:
    # Rename table back
    op.rename_table('access_policy_assignments', 'user_nas_privilege_map')
