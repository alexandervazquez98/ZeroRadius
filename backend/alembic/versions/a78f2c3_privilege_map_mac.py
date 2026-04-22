"""Add calling_station_id to user_nas_privilege_map

Revision ID: a78f2c3
Revises: 9879b9d
Create Date: 2026-04-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a78f2c3'
down_revision: Union[str, None] = '9879b9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column
    op.add_column('user_nas_privilege_map', sa.Column('calling_station_id', sa.String(length=50), nullable=True))
    
    # Update constraints
    # Drop old unique constraint
    # Note: dialect specific or generic? MySQL uses Index for Unique
    try:
        op.drop_constraint('uq_user_nas_ip', 'user_nas_privilege_map', type_='unique')
    except:
        pass # Might not exist as a constraint but as an index
        
    op.create_unique_constraint('uq_user_nas_ip_mac', 'user_nas_privilege_map', ['username', 'nas_ip', 'calling_station_id'])
    
    # Add index
    op.create_index('idx_unpm_mac', 'user_nas_privilege_map', ['calling_station_id'])


def downgrade() -> None:
    op.drop_index('idx_unpm_mac', table_name='user_nas_privilege_map')
    op.drop_constraint('uq_user_nas_ip_mac', 'user_nas_privilege_map', type_='unique')
    op.create_unique_constraint('uq_user_nas_ip', 'user_nas_privilege_map', ['username', 'nas_ip'])
    op.drop_column('user_nas_privilege_map', 'calling_station_id')
