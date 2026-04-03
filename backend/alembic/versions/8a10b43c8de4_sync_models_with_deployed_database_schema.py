"""sync models with deployed database schema

Revision ID: 8a10b43c8de4
Revises:
Create Date: 2026-04-03

This migration syncs the database schema with the SQLAlchemy models:
- Adds nas.zone_id and nas.category_id columns with FKs
- Adds user_nas_privilege_map.nas_category_id column with FK
- Changes radacct.acctinputoctets/acctoutputoctets from Integer to BigInteger
- Changes radpostauth.authdate from nullable=True to nullable=False
- Changes nas_categories.criticality from String(20) to Enum
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "8a10b43c8de4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the criticality enum type for MySQL
    # Note: MySQL handles enums differently, so we'll use a string column with a check constraint
    # For now, we'll keep it as VARCHAR but the model uses Enum for validation

    # 1. Add nas.zone_id column
    op.add_column("nas", sa.Column("zone_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_nas_zone", "nas", "hardware_zones", ["zone_id"], ["id"], ondelete="SET NULL"
    )

    # 2. Add nas.category_id column
    op.add_column("nas", sa.Column("category_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_nas_category",
        "nas",
        "nas_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 3. Add user_nas_privilege_map.nas_category_id column
    op.add_column(
        "user_nas_privilege_map",
        sa.Column("nas_category_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_unpm_category",
        "user_nas_privilege_map",
        "nas_categories",
        ["nas_category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_unpm_category", "user_nas_privilege_map", ["nas_category_id"])

    # 4. Change radacct.acctinputoctets from Integer to BigInteger
    op.alter_column(
        "radacct",
        "acctinputoctets",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )

    # 5. Change radacct.acctoutputoctets from Integer to BigInteger
    op.alter_column(
        "radacct",
        "acctoutputoctets",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )

    # 5b. Change radacct.radacctid from Integer to BigInteger
    op.alter_column(
        "radacct",
        "radacctid",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )

    # 6. Change radpostauth.authdate from nullable=True to nullable=False
    # First set a default value for any existing NULL rows
    op.execute("UPDATE radpostauth SET authdate = NOW() WHERE authdate IS NULL")
    op.execute(
        "ALTER TABLE radpostauth MODIFY COLUMN authdate DATETIME(6) NOT NULL "
        "DEFAULT CURRENT_TIMESTAMP(6)"
    )

    # 7. Change nas_categories.criticality from String(20) to Enum
    # Use ALTER TABLE MODIFY for atomic enum conversion in MySQL
    # Sanitize existing data first to avoid strict mode failures
    op.execute(
        "UPDATE nas_categories SET criticality = 'standard' "
        "WHERE criticality NOT IN ('critical', 'standard', 'restricted')"
    )
    op.execute(
        "ALTER TABLE nas_categories MODIFY COLUMN criticality "
        "ENUM('critical', 'standard', 'restricted') NOT NULL DEFAULT 'standard'"
    )


def downgrade() -> None:
    # 1. Drop nas.zone_id
    op.drop_constraint("fk_nas_zone", "nas", type_="foreignkey")
    op.drop_column("nas", "zone_id")

    # 2. Drop nas.category_id
    op.drop_constraint("fk_nas_category", "nas", type_="foreignkey")
    op.drop_column("nas", "category_id")

    # 3. Drop user_nas_privilege_map.nas_category_id
    op.drop_constraint("fk_unpm_category", "user_nas_privilege_map", type_="foreignkey")
    op.drop_index("idx_unpm_category", table_name="user_nas_privilege_map")
    op.drop_column("user_nas_privilege_map", "nas_category_id")

    # 4. Revert radacct columns to Integer
    op.alter_column(
        "radacct",
        "acctinputoctets",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "radacct",
        "acctoutputoctets",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "radacct",
        "radacctid",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )

    # 5. Revert radpostauth.authdate to nullable
    op.execute(
        "ALTER TABLE radpostauth MODIFY COLUMN authdate DATETIME(6) NULL "
        "DEFAULT CURRENT_TIMESTAMP(6)"
    )

    # 6. Revert nas_categories.criticality to String
    op.add_column(
        "nas_categories", sa.Column("criticality_old", sa.String(20), nullable=True)
    )
    op.execute("UPDATE nas_categories SET criticality_old = criticality")
    op.drop_column("nas_categories", "criticality")
    # Use raw SQL for the rename+type+default in a single atomic CHANGE COLUMN statement
    op.execute(
        "ALTER TABLE nas_categories CHANGE COLUMN criticality_old criticality "
        "VARCHAR(20) NOT NULL DEFAULT 'standard'"
    )
