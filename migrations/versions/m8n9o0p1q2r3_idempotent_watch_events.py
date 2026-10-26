"""idempotent watch-time events

Additive: one nullable column on video_watch_sessions, a unique index over it, and a
new video_watch_events table. No existing row is rewritten. Sessions written before
this revision keep client_session_id NULL and are never extended by the new contract.

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-10-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm8n9o0p1q2r3'
down_revision = 'l7m8n9o0p1q2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('video_watch_sessions', sa.Column('client_session_id', sa.String(length=64), nullable=True))
    op.create_index('uq_watch_sessions_client', 'video_watch_sessions',
                    ['user_id', 'game_id', 'client_session_id'], unique=True)
    op.create_table(
        'video_watch_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.String(length=80), nullable=False),
        sa.Column('seconds_credited', sa.Float(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['video_watch_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'event_id', name='uq_watch_events_session_event'),
    )
    op.create_index('idx_watch_events_session_id', 'video_watch_events', ['session_id'])


def downgrade():
    # The event rows are the only record of which chunks were already counted, and
    # dropping them would let a retried chunk be counted twice. Prior session totals
    # stay in video_watch_sessions.watch_duration_seconds either way.
    bind = op.get_bind()
    if bind.execute(sa.text('SELECT 1 FROM video_watch_events LIMIT 1')).first():
        raise RuntimeError('Refusing to downgrade: watch events record which chunks were counted.')
    op.drop_index('idx_watch_events_session_id', table_name='video_watch_events')
    op.drop_table('video_watch_events')
    op.drop_index('uq_watch_sessions_client', table_name='video_watch_sessions')
    with op.batch_alter_table('video_watch_sessions') as batch_op:
        batch_op.drop_column('client_session_id')
