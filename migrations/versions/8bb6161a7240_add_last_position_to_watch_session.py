"""add_last_position_to_watch_session

Revision ID: 8bb6161a7240
Revises: d1e2f3a4b5c6
Create Date: 2026-03-04 23:46:25.848207

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8bb6161a7240'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('video_watch_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_position_seconds', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('video_watch_sessions', schema=None) as batch_op:
        batch_op.drop_column('last_position_seconds')
