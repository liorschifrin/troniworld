"""Add index on Comment.author_name

Revision ID: 75e2188cbf52
Revises: k6l7m8n9o0p1
Create Date: 2026-03-15 16:44:14.789548

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '75e2188cbf52'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index('ix_comments_author_name', ['author_name'], unique=False)


def downgrade():
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_index('ix_comments_author_name')
