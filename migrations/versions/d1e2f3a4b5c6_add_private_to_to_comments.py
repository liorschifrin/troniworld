"""add private_to to comments

Revision ID: d1e2f3a4b5c6
Revises: b7d8e9f0a1b2
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'b7d8e9f0a1b2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('private_to', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_column('private_to')
