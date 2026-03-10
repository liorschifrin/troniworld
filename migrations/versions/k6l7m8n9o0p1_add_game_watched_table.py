"""add game_watched table

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0
Create Date: 2026-03-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'k6l7m8n9o0p1'
down_revision = 'j5k6l7m8n9o0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'game_watched',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('watched_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'game_id', name='uq_game_watched_user_game'),
    )
    op.create_index('idx_game_watched_user_id', 'game_watched', ['user_id'])
    op.create_index('idx_game_watched_game_id', 'game_watched', ['game_id'])


def downgrade():
    op.drop_index('idx_game_watched_game_id', table_name='game_watched')
    op.drop_index('idx_game_watched_user_id', table_name='game_watched')
    op.drop_table('game_watched')
