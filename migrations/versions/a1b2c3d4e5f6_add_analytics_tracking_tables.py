"""Add analytics tracking tables

Revision ID: a1b2c3d4e5f6
Revises: 0d6f3348d878
Create Date: 2026-02-26 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0d6f3348d878'
branch_labels = None
depends_on = None


def upgrade():
    # Create login_events table
    op.create_table('login_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('login_time', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    with op.batch_alter_table('login_events', schema=None) as batch_op:
        batch_op.create_index('idx_login_events_user_id', ['user_id'], unique=False)
        batch_op.create_index('idx_login_events_login_time', ['login_time'], unique=False)
    
    # Create video_watch_sessions table
    op.create_table('video_watch_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('game_id', sa.Integer(), nullable=False),
        sa.Column('watch_duration_seconds', sa.Integer(), nullable=False, default=0),
        sa.Column('session_start', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('last_updated', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    with op.batch_alter_table('video_watch_sessions', schema=None) as batch_op:
        batch_op.create_index('idx_watch_sessions_user_id', ['user_id'], unique=False)
        batch_op.create_index('idx_watch_sessions_game_id', ['game_id'], unique=False)
        batch_op.create_index('idx_watch_sessions_user_game', ['user_id', 'game_id'], unique=False)


def downgrade():
    # Drop video_watch_sessions table
    with op.batch_alter_table('video_watch_sessions', schema=None) as batch_op:
        batch_op.drop_index('idx_watch_sessions_user_game')
        batch_op.drop_index('idx_watch_sessions_game_id')
        batch_op.drop_index('idx_watch_sessions_user_id')
    
    op.drop_table('video_watch_sessions')
    
    # Drop login_events table
    with op.batch_alter_table('login_events', schema=None) as batch_op:
        batch_op.drop_index('idx_login_events_login_time')
        batch_op.drop_index('idx_login_events_user_id')
    
    op.drop_table('login_events')
