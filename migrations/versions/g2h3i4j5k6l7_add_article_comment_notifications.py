"""add article_comment_notifications table

Revision ID: g2h3i4j5k6l7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g2h3i4j5k6l7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'article_comment_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('recipient_username', sa.String(100), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(20), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['article_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['post.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_art_notifs_recipient', 'article_comment_notifications', ['recipient_username'])
    op.create_index('idx_art_notifs_recipient_unread', 'article_comment_notifications', ['recipient_username', 'is_read'])


def downgrade():
    op.drop_index('idx_art_notifs_recipient_unread', table_name='article_comment_notifications')
    op.drop_index('idx_art_notifs_recipient', table_name='article_comment_notifications')
    op.drop_table('article_comment_notifications')
