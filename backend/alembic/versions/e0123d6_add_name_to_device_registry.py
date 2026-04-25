"""add nullable name to device_registry

Revision ID: e0123d6
Revises: d0123d5
Create Date: 2026-04-24 09:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e0123d6"
down_revision: Union[str, None] = "d0123d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "device_registry" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("device_registry")}
    if "name" not in columns:
        op.add_column("device_registry", sa.Column("name", sa.String(length=120), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "device_registry" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("device_registry")}
    if "name" in columns:
        op.drop_column("device_registry", "name")
