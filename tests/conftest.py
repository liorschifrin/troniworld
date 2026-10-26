"""Import the global application only after isolating all runtime storage."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest
from flask import Flask

if 'flask_app' in sys.modules:
    raise RuntimeError('Application imported before test isolation was installed')

_runtime = TemporaryDirectory(prefix='troniworld-tests-')
_runtime_path = Path(_runtime.name)
os.environ.update(
    DATABASE_URI='sqlite:///:memory:',
    SECRET_KEY='synthetic-test-session-key',
    FILM_USER_PASSWORD='synthetic-member-password',
    FILM_ADMIN_PASSWORD='synthetic-admin-password',
    PYTHON_DOTENV_DISABLED='1',
)
_original_init = Flask.__init__
_original_makedirs = os.makedirs
_source_uploads = Path(__file__).resolve().parents[1] / 'flask_app/static/uploads'


def _isolated_init(self, *args, **kwargs):
    kwargs['instance_path'] = str(_runtime_path / 'instance')
    _original_init(self, *args, **kwargs)


def _isolated_makedirs(path, *args, **kwargs):
    # The global app creates this directory before configuration can be changed.
    destination = Path(path).resolve()
    if destination == _source_uploads:
        destination = _runtime_path / 'uploads'
    if not destination.is_relative_to(_runtime_path):
        raise RuntimeError('Unexpected import-time filesystem write')
    return _original_makedirs(destination, *args, **kwargs)


with patch.object(Flask, '__init__', _isolated_init), patch('os.makedirs', _isolated_makedirs):
    from flask_app import app as application, db as database

application.config.update(TESTING=True, UPLOAD_FOLDER=str(_runtime_path / 'uploads'))


def assert_isolated(upload_root=_runtime_path):
    assert application.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'
    assert set(database.engines) == {None}
    assert str(database.engine.url) == 'sqlite:///:memory:'
    assert Path(application.instance_path).is_relative_to(_runtime_path)
    assert Path(application.config['UPLOAD_FOLDER']).is_relative_to(upload_root)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(application.config, 'UPLOAD_FOLDER', str(tmp_path / 'uploads'))
    # tmp_path is independently managed by pytest; check it separately below.
    (tmp_path / 'uploads').mkdir()
    with application.app_context():
        assert_isolated(tmp_path)
        database.create_all()
        try:
            yield application
        finally:
            database.session.remove()
            assert_isolated(tmp_path)
            database.drop_all()
            database.engine.dispose()


with application.app_context():
    assert_isolated()


@pytest.fixture
def db(app):
    return database


@pytest.fixture
def records(db):
    from flask_app.models import Comment, Game, Point, User
    users = {role: User(username=role, hashed_password='synthetic-unused-hash',
                        is_admin=role == 'admin', is_leadership=role == 'leadership')
             for role in ('ordinary', 'admin', 'leadership', 'recipient')}
    game = Game(title='Synthetic public game', opponent='Synthetic visitors')
    hidden = Game(title='Synthetic hidden game', opponent='Synthetic visitors', is_hidden=True)
    db.session.add_all([*users.values(), game, hidden])
    db.session.flush()
    point = Point(game_id=game.id, point_index=1, timestamp_start=10)
    private = Comment(game_id=game.id, author_name='admin', content='Synthetic private marker',
                      comment_type='Comment', private_to='["recipient"]')
    db.session.add_all([point, private])
    db.session.commit()
    return dict(users=users, game=game, hidden=hidden, point=point, private=private)


@pytest.fixture
def client_for(app, records):
    # Shared clients act like a page from this site: their session holds a CSRF
    # token and every request sends it. tests/test_csrf.py covers denial paths.
    def make(role=None):
        client = app.test_client()
        token = f'synthetic-csrf-{role or "anonymous"}'
        with client.session_transaction() as session:
            session['csrf_token'] = token
            if role is not None:
                session['user_id'] = records['users'][role].id
        client.environ_base['HTTP_X_CSRFTOKEN'] = token
        return client
    return make


@pytest.fixture
def anonymous(client_for):
    return client_for()


@pytest.fixture
def ordinary(client_for):
    return client_for('ordinary')


@pytest.fixture
def admin(client_for):
    return client_for('admin')


@pytest.fixture
def leadership(client_for):
    return client_for('leadership')


def pytest_collection_modifyitems(config, items):
    # Browser tests need Chromium (python -m playwright install chromium); they run only when asked for with -m.
    if 'browser' in (config.option.markexpr or ''):
        return
    skip = pytest.mark.skip(reason='browser tests are opt-in: python -m pytest -m browser')
    for item in items:
        if 'browser' in item.keywords:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    with application.app_context():
        database.session.remove()
        database.engine.dispose()
    _runtime.cleanup()


def synthetic_image(fmt='PNG', size=(4, 4)):
    """Bytes of a tiny generated image; no real images are used in tests."""
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new('RGB', size, (10, 120, 200)).save(buffer, fmt)
    return buffer.getvalue()
