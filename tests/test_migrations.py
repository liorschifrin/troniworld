"""T07: bootstrap, upgrade-with-data, and model/schema drift on temporary SQLite files."""
import json
import os
import shutil
import sqlite3
import subprocess
import sys

import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from flask_app import db as database
from migration_support import (
    HEAD, ROOT, REVISIONS, build_snapshot, flask_command, seed, snapshot_metadata, table_rows,
)

# Revisions from which the shipped history reaches the head. Older revisions
# cannot (see test_history_before_f65e_cannot_reach_head).
UPGRADABLE = REVISIONS[REVISIONS.index('f65e956efdb9'):-1]


def stamped_revision(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute('SELECT version_num FROM alembic_version').fetchall()
    finally:
        conn.close()


def drift(path):
    engine = sa.create_engine(f'sqlite:///{path}')
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={'compare_type': True, 'compare_server_default': True})
            return sorted(describe(d) for d in compare_metadata(ctx, database.metadata))
    finally:
        engine.dispose()


def default_text(default):
    return str(getattr(default, 'arg', default)).replace('\n', ' ')


def describe(diff):
    items = diff if isinstance(diff, list) else [diff]
    out = []
    for item in items:
        kind = item[0]
        obj = item[1:]
        if kind in ('add_table', 'remove_table'):
            out.append(f'{kind} {obj[0].name}')
        elif kind in ('add_index', 'remove_index'):
            out.append(f'{kind} {obj[0].table.name}.{obj[0].name}')
        elif kind in ('add_column', 'remove_column'):
            out.append(f'{kind} {obj[1]}.{obj[2].name}')
        elif kind in ('add_constraint', 'remove_constraint'):
            out.append(f'{kind} {obj[0].table.name}.{obj[0].name}')
        elif kind in ('add_fk', 'remove_fk'):
            out.append(f'{kind} {obj[0].parent.name}.{obj[0].name or [c.name for c in obj[0].columns]}')
        else:
            if kind == 'modify_default':
                # (schema, table, column, kwargs, migrated default, model default)
                out.append(f'{kind} {obj[1]}.{obj[2]} migrated={default_text(obj[4])} model={default_text(obj[5])}')
            else:
                out.append(f'{kind} {obj[1]}.{obj[2]}')
    return ' | '.join(out)


def test_bootstrap_empty_database_matches_models(tmp_path):
    path = tmp_path / 'fresh.db'
    result = flask_command(path, 'bootstrap-db')
    assert result.returncode == 0, result.stderr
    assert stamped_revision(path) == [(HEAD,)]
    assert drift(path) == []
    result = flask_command(path, 'db', 'current')
    assert result.returncode == 0 and HEAD in result.stderr + result.stdout
    # An upgrade on the freshly stamped database is a no-op.
    assert flask_command(path, 'db', 'upgrade').returncode == 0
    assert stamped_revision(path) == [(HEAD,)]


def test_bootstrap_refuses_a_nonempty_database(tmp_path):
    path = tmp_path / 'old.db'
    build_snapshot(path, 'f1a2b3c4d5e6')
    seed(path, 'f1a2b3c4d5e6')
    before = table_rows(path)
    result = flask_command(path, 'bootstrap-db')
    assert result.returncode != 0 and 'not empty' in result.stderr
    assert table_rows(path) == before
    assert stamped_revision(path) == [('f1a2b3c4d5e6',)]


def test_replay_on_an_empty_database_fails_at_the_first_user_alteration(tmp_path):
    result = flask_command(tmp_path / 'empty.db', 'db', 'upgrade')
    assert result.returncode != 0
    assert 'no such table: user' in result.stderr


@pytest.mark.parametrize('revision', UPGRADABLE)
def test_upgrade_from_prior_revision_preserves_data(tmp_path, revision):
    path = tmp_path / 'old.db'
    build_snapshot(path, revision)
    seed(path, revision)
    before = table_rows(path)
    assert all(before[t] for t in before), 'every table is seeded'
    backup = tmp_path / 'backup.db'
    shutil.copyfile(path, backup)

    result = flask_command(path, 'db', 'upgrade')
    assert result.returncode == 0, result.stderr
    assert stamped_revision(path) == [(HEAD,)]

    after = table_rows(path)
    assert set(before) <= set(after)
    for table, old_rows in before.items():
        assert len(after[table]) == len(old_rows), f'{table} lost rows'
        new_rows = [{k: row[k] for k in old_rows[0] if k in row} for row in after[table]]
        old_kept = [{k: v for k, v in row.items() if k in new_rows[0]} for row in old_rows]
        assert new_rows == old_kept, table
    assert table_rows(backup) == before


def test_history_before_f65e_cannot_reach_head(tmp_path):
    """Characterization: 3ccbad256d39 and f65e956efdb9 both drop the same legacy tables."""
    path = tmp_path / 'old.db'
    build_snapshot(path, 'c9c8714eb81b')
    result = flask_command(path, 'db', 'upgrade')
    assert result.returncode != 0
    assert 'no such table' in result.stderr


# Differences between the models and a database migrated from the oldest
# upgradable snapshot (T07 drift report; nothing here is fixed by T07). A
# database made by `flask bootstrap-db` has none of them. New drift, or drift
# that is fixed, fails the test so this list stays an honest record.
KNOWN_MIGRATION_DRIFT = [
    # Models declare index=True (ix_*) on columns whose migrations created only the explicit idx_* index.
    'add_index article_comment_notifications.ix_article_comment_notifications_comment_id',
    'add_index article_comment_notifications.ix_article_comment_notifications_post_id',
    'add_index article_comment_notifications.ix_article_comment_notifications_recipient_username',
    'add_index comment_notifications.ix_comment_notifications_comment_id',
    'add_index comment_notifications.ix_comment_notifications_game_id',
    'add_index comment_notifications.ix_comment_notifications_recipient_username',
    'add_index game_watched.ix_game_watched_game_id',
    'add_index game_watched.ix_game_watched_user_id',
    'add_index login_events.ix_login_events_user_id',
    'add_index video_watch_sessions.ix_video_watch_sessions_game_id',
    'add_index video_watch_sessions.ix_video_watch_sessions_user_id',
    # Migrations set server defaults the models do not declare.
    "modify_default article_comment_notifications.created_at migrated=(CURRENT_TIMESTAMP) model=None",
    "modify_default article_comment_notifications.is_read migrated=0 model=None",
    "modify_default comment_notifications.created_at migrated=(CURRENT_TIMESTAMP) model=None",
    "modify_default comment_notifications.is_read migrated=0 model=None",
    "modify_default post.created_at migrated=(CURRENT_TIMESTAMP) model=None",
    "modify_default user.is_admin migrated='0' model=None",
    "modify_default user.is_leadership migrated='0' model=None",
    # Migration e1f2a3b4c5d6 made an index the model does not declare.
    'remove_index comment_notifications.idx_notifs_comment_id',
]
# Not detected here: CHECK constraints (the models' comment_type_check was never migrated;
# SQLite reflection does not report it) and anything outside tables/columns/indexes/defaults/FKs.


def test_migrated_schema_drift_is_the_recorded_list(tmp_path):
    path = tmp_path / 'migrated.db'
    build_snapshot(path, UPGRADABLE[0])
    assert flask_command(path, 'db', 'upgrade').returncode == 0
    assert drift(path) == KNOWN_MIGRATION_DRIFT


@pytest.mark.parametrize('revision', UPGRADABLE[1:])
def test_every_upgrade_path_ends_with_the_same_schema(tmp_path, revision):
    oldest, other = tmp_path / 'oldest.db', tmp_path / 'other.db'
    build_snapshot(oldest, UPGRADABLE[0])
    build_snapshot(other, revision)
    assert flask_command(oldest, 'db', 'upgrade').returncode == 0
    assert flask_command(other, 'db', 'upgrade').returncode == 0
    assert drift(other) == drift(oldest)


def test_backup_restore_rehearsal(tmp_path):
    """Back up before an upgrade, upgrade, restore the backup, and upgrade again."""
    live, backup = tmp_path / 'live.db', tmp_path / 'backup.db'
    build_snapshot(live, 'e1f2a3b4c5d6')
    seed(live, 'e1f2a3b4c5d6')
    original = table_rows(live)

    # SQLite online backup API: a consistent copy even if the file is in use.
    source, target = sqlite3.connect(live), sqlite3.connect(backup)
    source.backup(target)
    source.close(), target.close()
    assert table_rows(backup) == original and stamped_revision(backup) == [('e1f2a3b4c5d6',)]

    assert flask_command(live, 'db', 'upgrade').returncode == 0
    assert stamped_revision(live) == [(HEAD,)]

    shutil.copyfile(backup, live)  # restore
    assert table_rows(live) == original
    assert {t: len(r) for t, r in table_rows(live).items()} == {t: len(r) for t, r in original.items()}
    assert stamped_revision(live) == [('e1f2a3b4c5d6',)]
    assert flask_command(live, 'db', 'upgrade').returncode == 0
    assert stamped_revision(live) == [(HEAD,)]


def test_orphan_row_rolls_the_whole_upgrade_back(tmp_path):
    path = tmp_path / 'orphan.db'
    build_snapshot(path, 'j5k6l7m8n9o0')
    seed(path, 'j5k6l7m8n9o0')
    conn = sqlite3.connect(path)  # foreign keys are off on a raw connection
    conn.execute('INSERT INTO login_events (id, user_id, login_time) VALUES (99, 12345, "2026-01-01 00:00:00")')
    conn.commit()
    conn.close()
    before = table_rows(path)
    result = flask_command(path, 'db', 'upgrade')
    assert result.returncode != 0
    assert 'rolled back' in result.stderr and 'login_events' in result.stderr
    assert stamped_revision(path) == [('j5k6l7m8n9o0',)]
    assert table_rows(path) == before
    assert 'game_watched' not in {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master")}


# A tiny migrations tree (the real env.py plus two throwaway revisions) for pragma-restore checks.
REVISION_ONE = """
revision = 'aaaa00000001'
down_revision = None
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('scratch', sa.Column('id', sa.Integer(), primary_key=True))

def downgrade():
    op.drop_table('scratch')
"""
REVISION_TWO = REVISION_ONE.replace("'aaaa00000001'", "'aaaa00000002'").replace(
    "down_revision = None", "down_revision = 'aaaa00000001'").replace(
    "op.create_table('scratch', sa.Column('id', sa.Integer(), primary_key=True))", "raise RuntimeError('boom')")


def run_driver(tmp_path, initial, failing):
    directory = tmp_path / 'migrations'
    (directory / 'versions').mkdir(parents=True)
    for name in ('env.py', 'alembic.ini', 'script.py.mako'):
        shutil.copyfile(ROOT / 'migrations' / name, directory / name)
    (directory / 'versions' / 'one.py').write_text(REVISION_ONE)
    if failing:
        (directory / 'versions' / 'two.py').write_text(REVISION_TWO)
    env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URI', 'SECRET_KEY')}
    result = subprocess.run([sys.executable, str(ROOT / 'tests' / 'migration_driver.py'), str(tmp_path / 'p.db'),
                             str(directory), str(initial)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.strip().splitlines()[-1])
    report['stderr'] = result.stderr
    return report


@pytest.mark.parametrize('initial', [1, 0])
def test_failing_migration_restores_the_original_foreign_key_setting(tmp_path, initial):
    report = run_driver(tmp_path, initial, failing=True)
    assert report['error'] and 'boom' in report['stderr']
    assert report['foreign_keys_after'] == initial
    assert 'scratch' not in report['tables'], 'the first revision was rolled back with the failing one'


@pytest.mark.parametrize('initial', [1, 0])
def test_successful_migration_restores_the_original_foreign_key_setting(tmp_path, initial):
    report = run_driver(tmp_path, initial, failing=False)
    assert report['error'] is None and 'scratch' in report['tables']
    assert report['foreign_keys_after'] == initial


def test_bootstrap_stamp_failure_leaves_an_empty_database(tmp_path):
    path = tmp_path / 'stampfail.db'
    script = (
        "from flask_app import app, bootstrap\n"
        "def broken(**kwargs):\n"
        "    raise RuntimeError('stamp failed')\n"
        "with app.app_context():\n"
        "    bootstrap.stamp = broken\n"
        "    try:\n"
        "        bootstrap.bootstrap_database()\n"
        "    except RuntimeError as error:\n"
        "        print('raised', error)\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URI', 'SECRET_KEY')}
    env.update(DATABASE_URI=f'sqlite:///{path}', SECRET_KEY='synthetic-migration-key', PYTHON_DOTENV_DISABLED='1')
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert 'raised stamp failed' in result.stdout, result.stderr
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    conn.close()
    assert flask_command(path, 'bootstrap-db').returncode == 0
    assert stamped_revision(path) == [(HEAD,)]
