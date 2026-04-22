"""Fix data integrity and CIDR math

Revision ID: b92d5e1
Revises: a78f2c3
Create Date: 2026-04-22 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision: str = 'b92d5e1'
down_revision: Union[str, None] = 'a78f2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add target_key
    op.add_column('user_nas_privilege_map', sa.Column('target_key', sa.String(length=128), nullable=True))
    
    # 2. Populate target_key using SQL hash (MySQL specific SHA2 used in manual migration, 
    # but we can do a simple concat hash here for generality or just text() for MySQL)
    conn = op.get_bind()
    conn.execute(text("""
        UPDATE user_nas_privilege_map
        SET target_key = SHA2(CONCAT(
            username, '|',
            COALESCE(nas_ip, ''), '|',
            COALESCE(calling_station_id, ''), '|',
            COALESCE(nas_category_id, '0'), '|',
            COALESCE(segment_id, '0'), '|',
            COALESCE(target_start_ip, ''), '|',
            COALESCE(target_end_ip, '')
        ), 256)
    """))
    
    op.alter_column('user_nas_privilege_map', 'target_key', existing_type=sa.String(length=128), nullable=False)
    op.create_unique_constraint('uq_unpm_target_key', 'user_nas_privilege_map', ['target_key'])
    
    # 3. Drop old unreliable constraints
    try:
        op.drop_constraint('uq_user_nas_ip_mac', 'user_nas_privilege_map', type_='unique')
    except:
        pass
    try:
        op.drop_constraint('uq_user_nas_cat', 'user_nas_privilege_map', type_='unique')
    except:
        pass
    try:
        op.drop_constraint('uq_user_segment_target', 'user_nas_privilege_map', type_='unique')
    except:
        pass

    # 4. Update View
    op.execute("DROP VIEW IF EXISTS nas_cidr_ranges")
    op.execute("""
        CREATE VIEW nas_cidr_ranges AS
        SELECT
            n.id,
            n.nasname,
            n.category_id,
            nc.name        AS category_name,
            nc.criticality AS category_criticality,
            (INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1)) & 
             (0xFFFFFFFF << (32 - CAST(
                    CASE WHEN LOCATE('/', n.nasname) > 0
                        THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                        ELSE '32'
                    END AS UNSIGNED)))) AS net_start,
            (INET_ATON(SUBSTRING_INDEX(n.nasname, '/', 1)) & 
             (0xFFFFFFFF << (32 - CAST(
                    CASE WHEN LOCATE('/', n.nasname) > 0
                        THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                        ELSE '32'
                    END AS UNSIGNED)))) 
                + POW(2, 32 - CAST(
                    CASE WHEN LOCATE('/', n.nasname) > 0
                        THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                        ELSE '32'
                    END AS UNSIGNED)) - 1              AS net_end,
            CAST(
                CASE WHEN LOCATE('/', n.nasname) > 0
                    THEN SUBSTRING_INDEX(n.nasname, '/', -1)
                    ELSE '32'
                END AS UNSIGNED)                       AS prefix_len
        FROM nas n
        JOIN nas_categories nc ON n.category_id = nc.id
    """)


def downgrade() -> None:
    # Approximate restoration of old state
    op.drop_constraint('uq_unpm_target_key', 'user_nas_privilege_map', type_='unique')
    op.drop_column('user_nas_privilege_map', 'target_key')
    
    op.create_unique_constraint('uq_user_nas_ip_mac', 'user_nas_privilege_map', ['username', 'nas_ip', 'calling_station_id'])
    op.create_unique_constraint('uq_user_nas_cat', 'user_nas_privilege_map', ['username', 'nas_category_id'])
    op.create_unique_constraint('uq_user_segment_target', 'user_nas_privilege_map', ['username', 'segment_id', 'segment_target_key'])
