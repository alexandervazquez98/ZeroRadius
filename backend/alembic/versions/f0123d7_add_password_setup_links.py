"""add password_setup_links (self-service password setup, #101 part C)

Revision ID: f0123d7
Revises: e0123d6
Create Date: 2026-11-21 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "f0123d7"
down_revision: Union[str, None] = "e0123d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# DATETIME(6) on MySQL/MariaDB, matching init.sql on fresh installs.
_DT = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def upgrade() -> None:
    bind = op.get_bind()
    if "password_setup_links" in inspect(bind).get_table_names():
        return  # created by init.sql on fresh installs

    op.create_table(
        "password_setup_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("radcheck_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_type", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", _DT, server_default=sa.text("CURRENT_TIMESTAMP(6)"), nullable=True),
        sa.Column("expires_at", _DT, nullable=False),
        sa.Column("used_at", _DT, nullable=True),
        sa.Column("revoked_at", _DT, nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_password_setup_links_token_hash"),
    )
    op.create_index(
        "ix_password_setup_links_radcheck_id", "password_setup_links", ["radcheck_id"]
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "password_setup_links" not in inspect(bind).get_table_names():
        return
    op.drop_index("ix_password_setup_links_radcheck_id", table_name="password_setup_links")
    op.drop_table("password_setup_links")
