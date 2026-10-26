"""add user.archived_at (archive instead of delete)

Additive: one nullable column, no default, no data rewrite, no table rebuild.
NULL means the account is active, so every existing row keeps working.

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-10-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'l7m8n9o0p1q2'
down_revision = 'k6l7m8n9o0p1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('archived_at', sa.DateTime(), nullable=True))


def downgrade():
    # Dropping the column would make archived accounts active again (able to log in),
    # so refuse while any account is archived.
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM "user" WHERE archived_at IS NOT NULL LIMIT 1')).first():
        raise RuntimeError('Refusing to downgrade: archived users would become active.')
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('archived_at')
