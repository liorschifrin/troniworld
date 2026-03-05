"""add comment_notifications table

Revision ID: e1f2a3b4c5d6
Revises: 8bb6161a7240
Create Date: 2026-03-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = '8bb6161a7240'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'comment_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_username', sa.String(100), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(20), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('comment_notifications', schema=None) as batch_op:
        batch_op.create_index('idx_notifs_recipient', ['recipient_username'])
        batch_op.create_index('idx_notifs_recipient_unread', ['recipient_username', 'is_read'])
        batch_op.create_index('idx_notifs_comment_id', ['comment_id'])


def downgrade():
    with op.batch_alter_table('comment_notifications', schema=None) as batch_op:
        batch_op.drop_index('idx_notifs_recipient')
        batch_op.drop_index('idx_notifs_recipient_unread')
        batch_op.drop_index('idx_notifs_comment_id')
    op.drop_table('comment_notifications')
