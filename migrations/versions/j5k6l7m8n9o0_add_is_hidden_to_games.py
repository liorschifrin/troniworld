"""add is_hidden to games

Revision ID: j5k6l7m8n9o0
Revises: i4j5k6l7m8n9
Create Date: 2026-03-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j5k6l7m8n9o0'
down_revision = 'i4j5k6l7m8n9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('games', sa.Column('is_hidden', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('games', 'is_hidden')
