"""add injury_subs to points

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-03-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i4j5k6l7m8n9'
down_revision = 'h3i4j5k6l7m8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('points', sa.Column('injury_subs', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('points', 'injury_subs')
