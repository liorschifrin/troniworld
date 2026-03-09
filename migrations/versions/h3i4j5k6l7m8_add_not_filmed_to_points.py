"""add not_filmed to points

Revision ID: h3i4j5k6l7m8
Revises: g2h3i4j5k6l7
Create Date: 2026-03-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h3i4j5k6l7m8'
down_revision = 'g2h3i4j5k6l7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('points', sa.Column('not_filmed', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('points', 'not_filmed')
