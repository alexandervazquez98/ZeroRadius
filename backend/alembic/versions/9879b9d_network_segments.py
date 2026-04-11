"""Add network_segments table and segment_id FK

Revision ID: 9879b9d
Revises: 8a10b43c8de4
Create Date: 2026-04-11

This migration:
- Creates the network_segments table
- Adds segment_id column to user_nas_privilege_map
- Creates FK with ON DELETE RESTRICT
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "9879b9d"
down_revision: Union[str, None] = "8a10b43c8de4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create network_segments table
    op.create_table(
        "network_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cidr", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=False),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            server_onupdate=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_general_ci",
    )
    op.create_index("idx_ns_name", "network_segments", ["name"])

    # 2. Add segment_id column to user_nas_privilege_map
    op.add_column(
        "user_nas_privilege_map",
        sa.Column("segment_id", sa.Integer(), nullable=True),
    )

    # 3. Create index for the FK
    op.create_index("idx_unpm_segment", "user_nas_privilege_map", ["segment_id"])

    # 4. Create FK with ON DELETE RESTRICT (not SET NULL)
    op.create_foreign_key(
        "fk_unpm_segment",
        "user_nas_privilege_map",
        "network_segments",
        ["segment_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # 1. Drop FK
    op.drop_constraint("fk_unpm_segment", "user_nas_privilege_map", type_="foreignkey")

    # 2. Drop index
    op.drop_index("idx_unpm_segment", table_name="user_nas_privilege_map")

    # 3. Drop segment_id column
    op.drop_column("user_nas_privilege_map", "segment_id")

    # 4. Drop network_segments table
    op.drop_index("idx_ns_name", table_name="network_segments")
    op.drop_table("network_segments")
