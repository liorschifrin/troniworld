"""Add tournaments and link games to tournaments

Revision ID: b7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 22:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7d8e9f0a1b2'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tournaments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('start_date', sa.String(length=10), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tournament_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('tournament_game_number', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_games_tournament_id'), ['tournament_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_games_tournament_id_tournaments',
            'tournaments',
            ['tournament_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    with op.batch_alter_table('games', schema=None) as batch_op:
        batch_op.drop_constraint('fk_games_tournament_id_tournaments', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_games_tournament_id'))
        batch_op.drop_column('tournament_game_number')
        batch_op.drop_column('tournament_id')

    op.drop_table('tournaments')
