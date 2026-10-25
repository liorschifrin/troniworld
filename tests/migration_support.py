"""Hand-written schema snapshots for migration tests.

The Alembic history cannot build a database from nothing, so a database "at"
revision X is built here from explicit DDL that mirrors what the deployed
schema looked like once X was applied. The tables the first revisions assume
(``user``, ``post``, ``players``, ``games``, ...) were created outside Alembic.
Snapshots are reconstructed from the revision files and models, not captured
from any real database.
"""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]

# Linear history, oldest first.
REVISIONS = [
    '3cf0153b0d39', '88ebf2c498ab', '3ccbad256d39', 'c9c8714eb81b', 'f65e956efdb9',
    '0d6f3348d878', 'a1b2c3d4e5f6', 'b7d8e9f0a1b2', 'd1e2f3a4b5c6', '8bb6161a7240',
    'e1f2a3b4c5d6', 'f1a2b3c4d5e6', 'g2h3i4j5k6l7', 'h3i4j5k6l7m8', 'i4j5k6l7m8n9',
    'j5k6l7m8n9o0', 'k6l7m8n9o0p1',
]
HEAD = REVISIONS[-1]


def snapshot_metadata(revision):
    """Tables and columns present in a database stamped at ``revision``."""
    n = REVISIONS.index(revision)

    def has(rev):
        return n >= REVISIONS.index(rev)

    md = sa.MetaData()
    C, T, I = sa.Column, sa.Table, sa.Integer
    S, B, DT = sa.String, sa.Boolean, sa.DateTime

    user_cols = [C('id', I, primary_key=True), C('username', S(255), nullable=False, unique=True),
                 C('hashed_password', S(255), nullable=False), C('is_admin', B, nullable=False, server_default='0')]
    if has('0d6f3348d878'):
        user_cols += [C('is_leadership', B, nullable=False, server_default='0'),
                      C('player_id', I, sa.ForeignKey('players.id', ondelete='SET NULL'))]
        if not has('f1a2b3c4d5e6'):
            user_cols.append(C('is_film_user', B, nullable=False, server_default='0'))
    T('user', md, *user_cols)

    post_cols = [C('id', I, primary_key=True), C('title', S(255), nullable=False),
                 C('author', S(255), nullable=False), C('content', sa.Text, nullable=False)]
    if has('88ebf2c498ab'):
        post_cols.append(C('created_at', DT, nullable=False, server_default=sa.func.current_timestamp()))
    T('post', md, *post_cols)

    T('players', md, C('id', I, primary_key=True), C('name', S(100), nullable=False, unique=True),
      C('jersey_number', I), C('active', B))
    game_cols = [C('id', I, primary_key=True), C('title', S(255), nullable=False),
                 C('opponent', S(100), nullable=False), C('youtube_id', S(20)), C('game_date', S(10)),
                 C('final_score_tron', I), C('final_score_opponent', I)]
    if has('f65e956efdb9'):
        game_cols.append(C('player_order_data', sa.JSON))
    if has('b7d8e9f0a1b2'):
        T('tournaments', md, C('id', I, primary_key=True), C('name', S(255), nullable=False), C('start_date', S(10)))
        game_cols += [C('tournament_id', I, sa.ForeignKey('tournaments.id', ondelete='SET NULL'), index=True),
                      C('tournament_game_number', I)]
    if has('j5k6l7m8n9o0'):
        game_cols.append(C('is_hidden', B, nullable=False, server_default='0'))
    T('games', md, *game_cols)

    point_cols = [C('id', I, primary_key=True), C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
                  C('point_index', I, nullable=False), C('timestamp_start', I), C('tron_o', B), C('tron_point', B),
                  C('pull_play', S(50)), C('defense_type', S(50)), C('offense_faced', S(50)),
                  sa.UniqueConstraint('game_id', 'point_index', name='_game_point_uc')]
    if has('h3i4j5k6l7m8'):
        point_cols.append(C('not_filmed', B, nullable=False, server_default='0'))
    if has('i4j5k6l7m8n9'):
        point_cols.append(C('injury_subs', sa.JSON))
    T('points', md, *point_cols)
    T('point_players', md, C('point_id', I, sa.ForeignKey('points.id', ondelete='CASCADE'), primary_key=True),
      C('player_id', I, sa.ForeignKey('players.id', ondelete='CASCADE'), primary_key=True))
    T('game_roster', md, C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), primary_key=True),
      C('player_id', I, sa.ForeignKey('players.id', ondelete='CASCADE'), primary_key=True))
    T('events', md, C('id', I, primary_key=True), C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
      C('point_id', I, sa.ForeignKey('points.id', ondelete='CASCADE')), C('event_type', S(20), nullable=False),
      C('team', S(20)), C('timestamp', I), C('created_at', DT))
    comment_cols = [C('id', I, primary_key=True), C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
                    C('point_id', I, sa.ForeignKey('points.id', ondelete='SET NULL')),
                    C('parent_id', I, sa.ForeignKey('comments.id', ondelete='CASCADE')),
                    C('comment_type', S(20), nullable=False), C('author_name', S(100), nullable=False),
                    C('timestamp', I), C('content', sa.Text, nullable=False), C('created_at', DT)]
    if has('d1e2f3a4b5c6'):
        comment_cols.append(C('private_to', sa.Text))
    T('comments', md, *comment_cols)
    T('article_comments', md, C('id', I, primary_key=True),
      C('post_id', I, sa.ForeignKey('post.id', ondelete='CASCADE'), nullable=False),
      C('parent_id', I, sa.ForeignKey('article_comments.id', ondelete='CASCADE')),
      C('author_name', S(100), nullable=False), C('content', sa.Text, nullable=False), C('created_at', DT))

    if has('a1b2c3d4e5f6'):
        T('login_events', md, C('id', I, primary_key=True),
          C('user_id', I, sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False), C('login_time', DT, nullable=False))
        watch = [C('id', I, primary_key=True), C('user_id', I, sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
                 C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
                 C('watch_duration_seconds', I, nullable=False), C('session_start', DT, nullable=False),
                 C('last_updated', DT, nullable=False)]
        if has('8bb6161a7240'):
            watch.append(C('last_position_seconds', sa.Float))
        T('video_watch_sessions', md, *watch)
    if has('e1f2a3b4c5d6'):
        T('comment_notifications', md, C('id', I, primary_key=True), C('recipient_username', S(100), nullable=False),
          C('comment_id', I, sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False),
          C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False),
          C('notification_type', S(20), nullable=False), C('is_read', B, nullable=False, server_default=sa.false()),
          C('created_at', DT, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')), C('read_at', DT))
    if has('g2h3i4j5k6l7'):
        T('article_comment_notifications', md, C('id', I, primary_key=True), C('recipient_username', S(100), nullable=False),
          C('comment_id', I, sa.ForeignKey('article_comments.id', ondelete='CASCADE'), nullable=False),
          C('post_id', I, sa.ForeignKey('post.id', ondelete='CASCADE'), nullable=False),
          C('notification_type', S(20), nullable=False), C('is_read', B, nullable=False, server_default=sa.false()),
          C('created_at', DT, nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')), C('read_at', DT))
    if has('k6l7m8n9o0p1'):
        T('game_watched', md, C('id', I, primary_key=True), C('user_id', I, sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
          C('game_id', I, sa.ForeignKey('games.id', ondelete='CASCADE'), nullable=False), C('watched_at', DT, nullable=False),
          sa.UniqueConstraint('user_id', 'game_id', name='uq_game_watched_user_game'))
    # Indexes that the table-creating migrations made.
    explicit = [('a1b2c3d4e5f6', 'login_events', 'idx_login_events_user_id', ['user_id']),
                ('a1b2c3d4e5f6', 'login_events', 'idx_login_events_login_time', ['login_time']),
                ('a1b2c3d4e5f6', 'video_watch_sessions', 'idx_watch_sessions_user_id', ['user_id']),
                ('a1b2c3d4e5f6', 'video_watch_sessions', 'idx_watch_sessions_game_id', ['game_id']),
                ('a1b2c3d4e5f6', 'video_watch_sessions', 'idx_watch_sessions_user_game', ['user_id', 'game_id']),
                ('e1f2a3b4c5d6', 'comment_notifications', 'idx_notifs_recipient', ['recipient_username']),
                ('e1f2a3b4c5d6', 'comment_notifications', 'idx_notifs_recipient_unread', ['recipient_username', 'is_read']),
                ('e1f2a3b4c5d6', 'comment_notifications', 'idx_notifs_comment_id', ['comment_id']),
                ('g2h3i4j5k6l7', 'article_comment_notifications', 'idx_art_notifs_recipient', ['recipient_username']),
                ('g2h3i4j5k6l7', 'article_comment_notifications', 'idx_art_notifs_recipient_unread', ['recipient_username', 'is_read']),
                ('k6l7m8n9o0p1', 'game_watched', 'idx_game_watched_user_id', ['user_id']),
                ('k6l7m8n9o0p1', 'game_watched', 'idx_game_watched_game_id', ['game_id'])]
    for rev, table, name, columns in explicit:
        if has(rev):
            sa.Index(name, *[md.tables[table].c[c] for c in columns])
    # What db.create_all() gave these tables before the history began.
    for table, columns in (('comments', ('game_id', 'parent_id')), ('events', ('game_id',)),
                           ('article_comments', ('post_id', 'parent_id')), ('game_roster', ('player_id',))):
        for column in columns:
            sa.Index(f'ix_{table}_{column}', md.tables[table].c[column])
            sa.Index(f'idx_{table}_{column}', md.tables[table].c[column])
    if has('c9c8714eb81b'):
        sa.Index('idx_point_players_player_id', md.tables['point_players'].c.player_id)
        sa.Index('ix_point_players_player_id', md.tables['point_players'].c.player_id)
        sa.Index('idx_points_game_id', md.tables['points'].c.game_id)
        sa.Index('ix_points_game_id', md.tables['points'].c.game_id)
    return md


def build_snapshot(path, revision):
    """Create a database file shaped like ``revision`` and stamp it there."""
    engine = sa.create_engine(f'sqlite:///{path}')
    snapshot_metadata(revision).create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, '
                             'CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))'))
        conn.execute(sa.text('INSERT INTO alembic_version VALUES (:r)'), {'r': revision})
    engine.dispose()


def flask_command(database_path, *args):
    """Run ``flask <args>`` against a temporary SQLite file in a fresh process."""
    env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URI', 'SECRET_KEY')}
    env.update(DATABASE_URI=f'sqlite:///{database_path}', SECRET_KEY='synthetic-migration-key',
               PYTHON_DOTENV_DISABLED='1', FLASK_APP='app.py')
    return subprocess.run([sys.executable, '-m', 'flask', *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=300)


def table_rows(path, tables=None):
    """Return {table: sorted rows as dicts} for every user table (or ``tables``)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        names = tables or [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")]
        return {name: sorted((dict(r) for r in conn.execute(f'SELECT * FROM "{name}"')), key=repr) for name in names}
    finally:
        conn.close()


def seed(path, revision, rows_per_table=2):
    """Insert synthetic rows (ids 1..n; every foreign key points at id 1..n)."""
    md = snapshot_metadata(revision)
    conn = sqlite3.connect(path)
    try:
        for table in md.sorted_tables:
            for i in range(1, rows_per_table + 1):
                values = {}
                for col in table.columns:
                    t = col.type
                    if isinstance(t, sa.Boolean):
                        values[col.name] = i % 2
                    elif isinstance(t, sa.Integer):
                        values[col.name] = i
                    elif isinstance(t, sa.Float):
                        values[col.name] = 1.5 * i
                    elif isinstance(t, sa.DateTime):
                        values[col.name] = f'2026-01-0{i} 12:00:00.000000'
                    elif isinstance(t, sa.JSON):
                        values[col.name] = '{"seed": %d}' % i
                    else:
                        values[col.name] = f'{table.name}.{col.name}.{i}'
                if table.name == 'comments':
                    values['comment_type'] = 'Comment'
                cols = ', '.join(f'"{c}"' for c in values)
                conn.execute(f'INSERT INTO "{table.name}" ({cols}) VALUES ({", ".join("?" * len(values))})',
                             list(values.values()))
        conn.commit()
    finally:
        conn.close()
