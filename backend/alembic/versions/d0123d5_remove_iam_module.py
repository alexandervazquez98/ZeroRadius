"""remove IAM module

Revision ID: d0123d5
Revises: c0123d4
Create Date: 2026-04-23 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "d0123d5"
down_revision: Union[str, None] = "c0123d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # 1. Drop fk_nas_zone and zone_id from nas (if present)
    if "nas" in tables:
        columns = {col["name"] for col in inspector.get_columns("nas")}
        if "zone_id" in columns:
            fk_names = {
                fk["name"] for fk in inspector.get_foreign_keys("nas") if fk.get("name")
            }
            if "fk_nas_zone" in fk_names:
                op.drop_constraint("fk_nas_zone", "nas", type_="foreignkey")
            op.drop_column("nas", "zone_id")

    # 2. Drop IAM tables (if present)
    for table_name in (
        "role_zone_policies",
        "policy_macros",
        "iam_roles",
        "hardware_zones",
    ):
        if table_name in tables:
            op.drop_table(table_name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "hardware_zones" not in tables:
        op.create_table(
            "hardware_zones",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.UniqueConstraint("name", name="uq_hardware_zones_name"),
        )
        op.create_index("idx_hz_name", "hardware_zones", ["name"], unique=False)

    if "iam_roles" not in tables:
        op.create_table(
            "iam_roles",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.UniqueConstraint("name", name="uq_iam_roles_name"),
        )
        op.create_index("idx_ir_name", "iam_roles", ["name"], unique=False)

    if "policy_macros" not in tables:
        op.create_table(
            "policy_macros",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("attributes_json", sa.JSON(), nullable=True),
            sa.UniqueConstraint("name", name="uq_policy_macros_name"),
        )
        op.create_index("idx_pm_name", "policy_macros", ["name"], unique=False)

    if "role_zone_policies" not in tables:
        op.create_table(
            "role_zone_policies",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("zone_id", sa.Integer(), nullable=False),
            sa.Column("policy_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["role_id"], ["iam_roles.id"], ondelete="CASCADE", name="fk_rzp_role"
            ),
            sa.ForeignKeyConstraint(
                ["zone_id"],
                ["hardware_zones.id"],
                ondelete="CASCADE",
                name="fk_rzp_zone",
            ),
            sa.ForeignKeyConstraint(
                ["policy_id"],
                ["policy_macros.id"],
                ondelete="CASCADE",
                name="fk_rzp_policy",
            ),
            sa.UniqueConstraint("role_id", "zone_id", name="uq_role_zone_policy"),
        )

    # re-inspect nas after potential table recreations
    inspector = inspect(bind)
    if "nas" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("nas")}
        if "zone_id" not in columns:
            op.add_column("nas", sa.Column("zone_id", sa.Integer(), nullable=True))

        fk_names = {
            fk["name"] for fk in inspector.get_foreign_keys("nas") if fk.get("name")
        }
        if "fk_nas_zone" not in fk_names:
            op.create_foreign_key(
                "fk_nas_zone",
                "nas",
                "hardware_zones",
                ["zone_id"],
                ["id"],
                ondelete="SET NULL",
            )
