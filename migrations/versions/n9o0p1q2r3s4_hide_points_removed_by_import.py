"""points.hidden_by_import (hide, never delete, points a reimport no longer contains)

Additive: one NOT NULL boolean column with a server default of 0 and no data rewrite,
so every existing point stays visible. A reimport sets it to 1 on points the new CSV
omits; their comments, annotations and player links stay in the database and an admin
can restore them.

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-10-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'n9o0p1q2r3s4'
down_revision = 'm8n9o0p1q2r3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('points', sa.Column('hidden_by_import', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    # Dropping the column would make every hidden point visible again with stale data.
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM points WHERE hidden_by_import = 1 LIMIT 1')).first():
        raise RuntimeError('Refusing to downgrade: points hidden by a CSV import would reappear. '
                           'Restore them first.')
    with op.batch_alter_table('points') as batch_op:
        batch_op.drop_column('hidden_by_import')
