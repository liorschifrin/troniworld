"""T13: production configuration, storage layout, restore, smoke and rollback rehearsals.

Everything here uses synthetic data in temporary directories: no real database,
no secret, no host, no running server.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

from flask import Flask
import pytest

from flask_app import config as release_config
from flask_app.config import ConfigError, apply_config
from migration_support import HEAD, REVISIONS, ROOT, build_snapshot, flask_command, seed, table_rows

from conftest import synthetic_image

SECRET = 'synthetic-production-secret-0123456789abcdef'


def production_env(tmp_path, **overrides):
    env = {
        'APP_ENV': 'production',
        'SECRET_KEY': SECRET,
        'DATABASE_URI': f'sqlite:///{tmp_path}/data/app.db',
        'UPLOAD_DIR': str(tmp_path / 'data' / 'uploads'),
        'FILM_USER_PASSWORD': 'synthetic-member-password',
        'FILM_ADMIN_PASSWORD': 'synthetic-admin-password',
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


@pytest.fixture
def tree(tmp_path):
    """A stand-in code tree so 'inside the code tree' is decided against a temp dir."""
    root = tmp_path / 'release' / 'app'
    (root / 'flask_app').mkdir(parents=True)
    app = Flask('flask_app')
    app.root_path = str(root / 'flask_app')
    return app


# --- 1. production configuration -------------------------------------------------

def test_production_profile_turns_debug_off_and_secures_the_session(tmp_path, tree):
    apply_config(tree, production_env(tmp_path))
    assert tree.config['DEBUG'] is False and tree.config['TESTING'] is False
    assert tree.config['TEMPLATES_AUTO_RELOAD'] is False
    assert tree.config['SESSION_COOKIE_SECURE'] is True
    assert tree.config['SESSION_COOKIE_HTTPONLY'] is True
    assert tree.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert tree.config['PREFERRED_URL_SCHEME'] == 'https'


def test_production_secret_comes_from_the_environment(tmp_path, tree):
    apply_config(tree, production_env(tmp_path))
    assert tree.secret_key == SECRET
    assert tree.secret_key not in release_config.PLACEHOLDER_SECRETS
    other = production_env(tmp_path, SECRET_KEY='another-synthetic-secret-value-abcdef123456')
    apply_config(tree, other)
    assert tree.secret_key == other['SECRET_KEY']


@pytest.mark.parametrize('overrides, fragment', [
    ({'SECRET_KEY': None}, 'SECRET_KEY'),
    ({'SECRET_KEY': ''}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'short'}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'synthetic-test-session-key'}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'changeme'}, 'SECRET_KEY'),
    ({'SECRET_KEY': ' ' * 40}, 'SECRET_KEY'),
    ({'SECRET_KEY': 'a' + ' ' * 40}, 'SECRET_KEY'),
    ({'FILM_USER_PASSWORD': None}, 'FILM_USER_PASSWORD must be set'),
    ({'FILM_ADMIN_PASSWORD': ' '}, 'FILM_ADMIN_PASSWORD must be set'),
    ({'DATABASE_URI': None}, 'DATABASE_URI must be set'),
    ({'DATABASE_URI': 'sqlite:///:memory:'}, 'in-memory'),
    ({'DATABASE_URI': 'sqlite://'}, 'in-memory'),
    ({'DATABASE_URI': 'sqlite+pysqlite:///:memory:'}, 'in-memory'),
    ({'DATABASE_URI': 'sqlite:////tmp/x.db?mode=memory&uri=true'}, 'in-memory'),
    ({'DATABASE_URI': 'sqlite:///relative.db'}, 'absolute'),
    ({'DATABASE_URI': 'sqlite+pysqlite:///relative.db'}, 'absolute'),
    ({'UPLOAD_DIR': None}, 'UPLOAD_DIR must be set'),
    ({'UPLOAD_DIR': 'relative/uploads'}, 'absolute'),
])
def test_production_refuses_unsafe_or_missing_settings(tmp_path, tree, overrides, fragment):
    with pytest.raises(ConfigError, match=fragment):
        apply_config(tree, production_env(tmp_path, **overrides))


def test_production_accepts_an_explicit_sqlite_driver_url(tmp_path, tree):
    apply_config(tree, production_env(tmp_path, DATABASE_URI=f'sqlite+pysqlite:///{tmp_path}/data/app.db'))
    assert tree.config['SESSION_COOKIE_SECURE'] is True
    root = Path(tree.root_path).parent
    with pytest.raises(ConfigError, match='outside the code tree'):
        apply_config(tree, production_env(tmp_path, DATABASE_URI=f'sqlite+pysqlite:///{root}/app.db'))


def test_production_refuses_data_inside_the_code_tree(tmp_path, tree):
    root = Path(tree.root_path).parent
    with pytest.raises(ConfigError, match='outside the code tree'):
        apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(root / 'flask_app' / 'static' / 'uploads')))
    with pytest.raises(ConfigError, match='outside the code tree'):
        apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(root / 'uploads')))
    with pytest.raises(ConfigError, match='outside the code tree'):
        apply_config(tree, production_env(tmp_path, DATABASE_URI=f'sqlite:///{root}/instance/app.db'))
    # An ancestor of the tree would publish the code and everything beside it.
    with pytest.raises(ConfigError, match='not contain it'):
        apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(root.parent)))
    with pytest.raises(ConfigError, match='must not contain'):  # tmp_path also holds the database
        apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(tmp_path)))
    # A symlink into the tree is still inside it.
    link = tmp_path / 'link'
    link.symlink_to(root / 'flask_app' / 'static')
    with pytest.raises(ConfigError, match='outside the code tree'):
        apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(link / 'uploads')))


def test_production_refuses_an_upload_folder_that_would_publish_the_database(tmp_path, tree):
    data = tmp_path / 'data'
    for upload_dir in (data, tmp_path):
        with pytest.raises(ConfigError, match='must not contain the database'):
            apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(upload_dir)))
    apply_config(tree, production_env(tmp_path, UPLOAD_DIR=str(data / 'uploads')))  # a subdirectory is fine


def test_non_production_keeps_development_behaviour(tmp_path, tree):
    tree.secret_key = None
    apply_config(tree, {'APP_ENV': 'development'})
    assert tree.config['UPLOAD_FOLDER'] == os.path.join(tree.root_path, 'static', 'uploads')
    assert tree.secret_key is None
    assert tree.config.get('SESSION_COOKIE_SECURE', False) is False
    assert not release_config.is_production({'APP_ENV': 'development'})
    assert release_config.is_production({'APP_ENV': 'production'})


@pytest.mark.parametrize('value', [None, '', ' ', 'prod', 'Productionn', 'Production', ' production', 'production ',
                                   'staging', 'dev', 'Development', 'true'])
def test_a_missing_or_misspelled_app_env_refuses_to_configure(tmp_path, tree, value):
    environ = production_env(tmp_path, APP_ENV=value)
    with pytest.raises(ConfigError, match='APP_ENV'):
        apply_config(tree, environ)
    with pytest.raises(ConfigError, match='APP_ENV'):
        release_config.is_production(environ)
    assert 'UPLOAD_FOLDER' not in tree.config  # nothing was configured


def test_the_real_app_module_refuses_to_start_with_a_missing_or_misspelled_app_env(tmp_path):
    for value in (None, 'prod', 'Productionn', ''):
        env = production_env(tmp_path, APP_ENV=value)
        result = subprocess.run([sys.executable, '-I', '-c', PRINT_CONFIG, str(ROOT)], env=clean_env(**env),
                                capture_output=True, text=True, timeout=120, cwd=tmp_path)
        assert result.returncode != 0 and 'APP_ENV' in result.stderr, value


def test_development_still_works_when_named_explicitly(tmp_path):
    env = {'APP_ENV': 'development', 'SECRET_KEY': 'x', 'DATABASE_URI': 'sqlite:///:memory:'}
    result = subprocess.run([sys.executable, '-I', '-c', PRINT_CONFIG, str(ROOT)],
                            env=clean_env(UPLOAD_DIR=str(tmp_path / 'dev-uploads'), **env),
                            capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded['TEMPLATES_AUTO_RELOAD'] is True and loaded['SESSION_COOKIE_SECURE'] is False


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ('DATABASE_URI', 'SECRET_KEY', 'APP_ENV', 'UPLOAD_DIR')}
    env.update(PYTHON_DOTENV_DISABLED='1', PYTHONDONTWRITEBYTECODE='1')
    env.update(extra)
    return env


PRINT_CONFIG = (
    "import json, sys; sys.path.insert(0, sys.argv[1]); from flask_app import app; "
    "print(json.dumps({k: app.config.get(k) for k in ('DEBUG','SESSION_COOKIE_SECURE','SESSION_COOKIE_HTTPONLY',"
    "'SESSION_COOKIE_SAMESITE','UPLOAD_FOLDER','TEMPLATES_AUTO_RELOAD')} | {'secret': app.secret_key}))"
)


def test_the_real_app_module_loads_the_production_profile(tmp_path):
    env = production_env(tmp_path)
    result = subprocess.run([sys.executable, '-I', '-c', PRINT_CONFIG, str(ROOT)], env=clean_env(**env),
                            capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    loaded = json.loads(result.stdout.strip().splitlines()[-1])
    assert loaded['DEBUG'] is False and loaded['TEMPLATES_AUTO_RELOAD'] is False
    assert loaded['SESSION_COOKIE_SECURE'] is True and loaded['SESSION_COOKIE_HTTPONLY'] is True
    assert loaded['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert loaded['secret'] == SECRET
    assert loaded['UPLOAD_FOLDER'] == env['UPLOAD_DIR'] and Path(env['UPLOAD_DIR']).is_dir()


def test_the_real_app_module_refuses_to_start_without_a_secret(tmp_path):
    env = production_env(tmp_path, SECRET_KEY=None)
    result = subprocess.run([sys.executable, '-I', '-c', PRINT_CONFIG, str(ROOT)], env=clean_env(**env),
                            capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert result.returncode != 0 and 'Production configuration refused' in result.stderr
    assert not Path(env['UPLOAD_DIR']).exists()


def test_the_documented_environment_variables_are_in_the_runbook():
    runbook = (ROOT / 'docs' / 'runbook.md').read_text()
    for name in ('APP_ENV', 'SECRET_KEY', 'DATABASE_URI', 'UPLOAD_DIR',
                 'FILM_USER_PASSWORD', 'FILM_ADMIN_PASSWORD'):
        assert name in runbook


# --- 2. database and uploads outside the code tree --------------------------------

def test_the_upload_path_is_configurable_and_not_in_static_code_paths(tmp_path, tree):
    apply_config(tree, production_env(tmp_path))
    folder = Path(tree.config['UPLOAD_FOLDER'])
    assert folder == tmp_path / 'data' / 'uploads'
    code = (ROOT / 'flask_app').resolve()
    assert not folder.resolve().is_relative_to(code)
    assert not folder.resolve().is_relative_to(code / 'static')
    # Without UPLOAD_DIR the development default is still the old location.
    apply_config(tree, {'APP_ENV': 'development'})
    assert tree.config['UPLOAD_FOLDER'].endswith(os.path.join('flask_app', 'static', 'uploads'))


def test_uploads_in_a_configured_folder_are_saved_and_served_at_the_public_url(app, client_for, records, tmp_path):
    outside = tmp_path / 'outside-code' / 'uploads'
    outside.mkdir(parents=True)
    app.config['UPLOAD_FOLDER'] = str(outside)
    admin = client_for('admin')
    data = synthetic_image()
    from io import BytesIO
    response = admin.post('/upload_image', data={'upload': (BytesIO(data), 'plan.png')},
                          content_type='multipart/form-data')
    assert response.status_code == 201, response.get_data(as_text=True)
    url = response.get_json()['url']
    name = url.rsplit('/', 1)[1]
    assert (outside / name).read_bytes() == data
    assert not (ROOT / 'flask_app' / 'static' / 'uploads' / name).exists()
    served = client_for().get(url)
    assert served.status_code == 200 and served.get_data() == data
    assert served.headers['X-Content-Type-Options'] == 'nosniff'
    assert client_for().get('/static/uploads/../app.db').status_code == 404
    assert client_for().get('/static/uploads/missing.png').status_code == 404


def test_symlinks_in_the_upload_folder_are_not_served(app, client_for, tmp_path):
    folder = Path(app.config['UPLOAD_FOLDER'])
    secret = tmp_path / 'private' / 'app.db'
    secret.parent.mkdir()
    secret.write_bytes(b'synthetic private database bytes')
    (folder / 'inside.png').write_bytes(synthetic_image())
    (folder / 'to-outside.png').symlink_to(secret)
    (folder / 'to-inside.png').symlink_to(folder / 'inside.png')
    (folder / 'dir-link').symlink_to(secret.parent, target_is_directory=True)
    (folder / 'real-dir').mkdir()
    (folder / 'real-dir' / 'nested.png').write_bytes(synthetic_image())
    client = client_for()
    assert client.get('/static/uploads/to-outside.png').status_code == 404
    assert client.get('/static/uploads/to-inside.png').status_code == 404
    assert client.get('/static/uploads/dir-link/app.db').status_code == 404
    assert b'synthetic private' not in client.get('/static/uploads/dir-link/app.db').get_data()
    ok = client.get('/static/uploads/inside.png')
    assert ok.status_code == 200 and ok.get_data() == synthetic_image()
    assert ok.headers['X-Content-Type-Options'] == 'nosniff'
    assert client.get('/static/uploads/real-dir/nested.png').status_code == 200
    assert client.get('/static/uploads/real-dir').status_code == 404  # a directory
    for bad in ('../private/app.db', '..%2Fprivate%2Fapp.db', '%2e%2e/private/app.db', 'real-dir/../../private/app.db'):
        assert client.get('/static/uploads/' + bad).status_code == 404, bad


def test_a_component_swapped_for_a_symlink_after_the_look_is_refused(app, client_for, tmp_path, monkeypatch):
    from flask_app import uploads
    folder = Path(app.config['UPLOAD_FOLDER'])
    secret = tmp_path / 'private-file'
    secret.write_bytes(b'synthetic private bytes')
    (folder / 'sub').mkdir()
    (folder / 'sub' / 'pic.png').write_bytes(synthetic_image())
    real_open = uploads._open_at
    swapped = []

    def swapping_open(name, flags, dir_fd):
        # The attacker wins the race: just before the component is opened it becomes a symlink.
        if name == 'pic.png' and not swapped:
            swapped.append(name)
            (folder / 'sub' / 'pic.png').unlink()
            (folder / 'sub' / 'pic.png').symlink_to(secret)
        return real_open(name, flags, dir_fd)

    monkeypatch.setattr(uploads, '_open_at', swapping_open)
    response = client_for().get('/static/uploads/sub/pic.png')
    assert swapped and response.status_code == 404
    assert b'synthetic private' not in response.get_data()
    swapped.clear()
    # The same for a directory component swapped for a symlink to a directory.
    (folder / 'dir').mkdir()
    (folder / 'dir' / 'x.png').write_bytes(synthetic_image())

    def swapping_dir(name, flags, dir_fd):
        if name == 'dir' and not swapped:
            swapped.append(name)
            (folder / 'dir' / 'x.png').unlink()
            (folder / 'dir').rmdir()
            (folder / 'dir').symlink_to(tmp_path, target_is_directory=True)
            (tmp_path / 'x.png').write_bytes(b'synthetic outside')
        return real_open(name, flags, dir_fd)

    monkeypatch.setattr(uploads, '_open_at', swapping_dir)
    assert client_for().get('/static/uploads/dir/x.png').status_code == 404


def test_other_unsafe_upload_paths_are_refused_and_headers_are_kept(app, client_for):
    folder = Path(app.config['UPLOAD_FOLDER'])
    (folder / 'ok.png').write_bytes(synthetic_image())
    client = client_for()
    for bad in ('/etc/passwd', 'a//b.png', './ok.png', 'ok.png/', 'ok.png/.', 'sub\\..\\ok.png', 'ok.png%00.txt'):
        assert client.get('/static/uploads/' + bad).status_code == 404, bad
    ok = client.get('/static/uploads/ok.png')
    assert ok.status_code == 200 and ok.mimetype == 'image/png'
    assert ok.headers['X-Content-Type-Options'] == 'nosniff'
    assert ok.headers['Content-Length'] == str(len(synthetic_image()))
    assert client.head('/static/uploads/ok.png').status_code == 200


# --- 3. backup and restore rehearsal ----------------------------------------------

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def backup_set(database, uploads, target):
    """The documented backup: SQLite online backup of the database plus a copy of the uploads."""
    target.mkdir(parents=True)
    source, copy = sqlite3.connect(database), sqlite3.connect(target / 'app.db')
    source.backup(copy)
    source.close(), copy.close()
    shutil.copytree(uploads, target / 'uploads')
    manifest = {p.name: sha256(p) for p in sorted((target / 'uploads').iterdir())}
    (target / 'uploads.sha256.json').write_text(json.dumps(manifest))


def restore_set(backup, destination):
    destination.mkdir(parents=True)
    shutil.copyfile(backup / 'app.db', destination / 'app.db')
    shutil.copytree(backup / 'uploads', destination / 'uploads')


def test_restore_rehearsal_brings_back_the_database_and_the_uploads(tmp_path):
    live = tmp_path / 'live'
    (live / 'uploads').mkdir(parents=True)
    build_snapshot(live / 'app.db', HEAD)
    seed(live / 'app.db', HEAD)
    images = {f'{n}_pic{n}.png': synthetic_image(size=(n + 1, n + 1)) for n in range(3)}
    for name, data in images.items():
        (live / 'uploads' / name).write_bytes(data)
    rows_before = table_rows(live / 'app.db')
    counts_before = {t: len(r) for t, r in rows_before.items()}
    assert sum(counts_before.values()) > 0

    backup = tmp_path / 'backup'
    backup_set(live / 'app.db', live / 'uploads', backup)

    shutil.rmtree(live)  # the host is lost
    restored = tmp_path / 'clean-host'
    restore_set(backup, restored)

    assert table_rows(restored / 'app.db') == rows_before
    assert {t: len(r) for t, r in table_rows(restored / 'app.db').items()} == counts_before
    conn = sqlite3.connect(restored / 'app.db')
    assert conn.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
    assert conn.execute('SELECT version_num FROM alembic_version').fetchall() == [(HEAD,)]
    conn.close()
    manifest = json.loads((backup / 'uploads.sha256.json').read_text())
    restored_files = {p.name: sha256(p) for p in sorted((restored / 'uploads').iterdir())}
    assert restored_files == manifest and set(restored_files) == set(images)
    assert all((restored / 'uploads' / n).read_bytes() == d for n, d in images.items())


def test_the_documented_restore_guard_refuses_a_dangling_symlink(tmp_path):
    runbook = (ROOT / 'docs' / 'runbook.md').read_text()
    start = runbook.index('for target in /srv/troniworld/data/app.db')
    guard = runbook[start:runbook.index('\ndone\n', start) + len('\ndone')]
    guard = guard.replace('/srv/troniworld/data', str(tmp_path / 'data'))

    def run():
        return subprocess.run(['bash', '-c', 'set -euo pipefail\n' + guard], capture_output=True, text=True)

    (tmp_path / 'data').mkdir()
    assert run().returncode == 0                                   # clean target: allowed
    (tmp_path / 'data' / 'app.db').symlink_to(tmp_path / 'nowhere')  # dangling symlink
    refused = run()
    assert refused.returncode != 0 and 'refusing' in refused.stderr
    (tmp_path / 'data' / 'app.db').unlink()
    (tmp_path / 'data' / 'uploads').symlink_to(tmp_path / 'nowhere', target_is_directory=True)
    assert run().returncode != 0
    (tmp_path / 'data' / 'uploads').unlink()
    (tmp_path / 'data' / 'app.db').write_bytes(b'live')            # an existing live file
    assert run().returncode != 0


# --- 4. staging smoke and permission checks (automated part) ----------------------

def login(client, username, password):
    return client.post('/login', data={'username': username, 'password': password})


def test_smoke_login_view_game_and_admin_route_refuses_non_admin(client_for, records):
    game_url = f'/film/games/{records["game"].id}'
    # Anonymous: the login page works, protected pages redirect to it.
    anonymous = client_for()
    assert anonymous.get('/login').status_code == 200
    assert anonymous.get(game_url).status_code == 302
    assert anonymous.get('/admin/users').location.split('?')[0].endswith('/login')

    # A member signs in with the form and views a game; the admin page refuses them.
    member = client_for()
    response = login(member, 'ordinary', os.environ['FILM_USER_PASSWORD'])
    assert response.status_code == 302 and not response.location.endswith('/login')
    assert member.get('/film/games').status_code == 200
    assert member.get(game_url).status_code == 200
    refused = member.get('/admin/users')
    assert refused.status_code == 302 and refused.location.endswith('/')
    assert member.get('/film/analytics').status_code in (302, 403)
    # The hidden game is a plain 404 to a member.
    assert member.get(f'/film/games/{records["hidden"].id}').status_code == 404

    # A wrong password does not sign in.
    bad = client_for()
    assert login(bad, 'ordinary', 'wrong').location.endswith('/login')
    assert bad.get(game_url).status_code == 302

    # An admin reaches the admin page.
    admin = client_for()
    assert login(admin, 'admin', os.environ['FILM_ADMIN_PASSWORD']).status_code == 302
    assert admin.get('/admin/users').status_code == 200


def test_smoke_checklist_in_the_runbook_names_automated_and_manual_parts():
    runbook = (ROOT / 'docs' / 'runbook.md').read_text()
    assert 'Automated part' in runbook and 'Manual part (not automated)' in runbook


# --- 5. rollback rehearsal --------------------------------------------------------

PREVIOUS = REVISIONS[REVISIONS.index(HEAD) - 1]

START_CHECK = (
    "import sys; sys.path.insert(0, sys.argv[1]); from flask_app import app, db; "
    "from flask_app.models import Game, User\n"
    "with app.app_context():\n"
    "    print('users', User.query.count(), 'games', Game.query.count())\n"
    "client = app.test_client()\n"
    "print('login', client.get('/login').status_code)\n"
)


def start_app_against(database, tmp_path):
    env = clean_env(APP_ENV='development', DATABASE_URI=f'sqlite:///{database}', SECRET_KEY='synthetic-rollback-key',
                    UPLOAD_DIR=str(tmp_path / 'rollback-uploads'))
    result = subprocess.run([sys.executable, '-I', '-c', START_CHECK, str(ROOT)], env=env,
                            capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_rollback_rehearsal_restores_the_pre_upgrade_snapshot_and_the_app_starts(tmp_path):
    live = tmp_path / 'live.db'
    build_snapshot(live, PREVIOUS)
    seed(live, PREVIOUS)
    before = table_rows(live)
    snapshot = tmp_path / 'pre-upgrade.db'
    source, copy = sqlite3.connect(live), sqlite3.connect(snapshot)
    source.backup(copy)
    source.close(), copy.close()

    # Deploy: upgrade a copy of the data to the new schema.
    assert flask_command(live, 'db', 'upgrade').returncode == 0
    conn = sqlite3.connect(live)
    assert conn.execute('SELECT version_num FROM alembic_version').fetchall() == [(HEAD,)]
    conn.close()
    assert start_app_against(live, tmp_path).splitlines()[-1] == 'login 200'

    # Rollback path A: the previous app artifact plus the compatible schema (downgrade one revision).
    downgraded = tmp_path / 'downgraded.db'
    shutil.copyfile(live, downgraded)
    assert flask_command(downgraded, 'db', 'downgrade', PREVIOUS).returncode == 0
    conn = sqlite3.connect(downgraded)
    assert conn.execute('SELECT version_num FROM alembic_version').fetchall() == [(PREVIOUS,)]
    conn.close()
    assert table_rows(downgraded) == before

    # Rollback path B: restore the snapshot taken before the upgrade.
    restored = tmp_path / 'restored.db'
    shutil.copyfile(snapshot, restored)
    assert table_rows(restored) == before
    conn = sqlite3.connect(restored)
    assert conn.execute('SELECT version_num FROM alembic_version').fetchall() == [(PREVIOUS,)]
    assert conn.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
    conn.close()
    # The restored copy opens under the application and can be upgraded again.
    assert 'users 2' in start_app_against(restored, tmp_path)
    assert flask_command(restored, 'db', 'upgrade').returncode == 0
