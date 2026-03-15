import os

# Must be set before importing flask_app — routes read these via os.getenv() at request time
os.environ.setdefault('FILM_ADMIN_PASSWORD', 'adminpass')
os.environ.setdefault('FILM_USER_PASSWORD', 'userpass')
os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('DATABASE_URI', 'sqlite:///:memory:')

import pytest
from sqlalchemy.pool import StaticPool
from werkzeug.security import generate_password_hash

from flask_app import app as flask_app, db as _db
from flask_app.models import User, Player, Game, Tournament, Point, Comment


@pytest.fixture(scope='session')
def app():
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_ENGINE_OPTIONS': {
            'connect_args': {'check_same_thread': False},
            'poolclass': StaticPool,
        },
        'WTF_CSRF_ENABLED': False,
    })
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_tables(app):
    """Wipe all rows after each test for isolation."""
    yield
    _db.session.rollback()
    for table in reversed(_db.metadata.sorted_tables):
        _db.session.execute(table.delete())
    _db.session.commit()


# ── Data factories ───────────────────────────────────────────────────────────

def make_admin(username='Admin'):
    u = User(
        username=username,
        hashed_password=generate_password_hash('adminpass'),
        is_admin=True,
        is_leadership=False,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


def make_user(username='Alice'):
    u = User(
        username=username,
        hashed_password=generate_password_hash('userpass'),
        is_admin=False,
        is_leadership=False,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


def make_leadership(username='Lead'):
    u = User(
        username=username,
        hashed_password=generate_password_hash('adminpass'),
        is_admin=False,
        is_leadership=True,
    )
    _db.session.add(u)
    _db.session.commit()
    return u


def make_game(title='Test Game', opponent='Rival', is_hidden=False):
    g = Game(title=title, opponent=opponent, is_hidden=is_hidden)
    _db.session.add(g)
    _db.session.commit()
    return g


def make_point(game_id, point_index=1, tron_o=True, tron_point=True):
    p = Point(
        game_id=game_id,
        point_index=point_index,
        tron_o=tron_o,
        tron_point=tron_point,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


def make_comment(game_id, author_name='Alice', content='Test comment',
                 comment_type='Comment', parent_id=None, private_to=None):
    import json
    c = Comment(
        game_id=game_id,
        author_name=author_name,
        content=content,
        comment_type=comment_type,
        parent_id=parent_id,
        private_to=json.dumps(private_to) if private_to is not None else None,
    )
    _db.session.add(c)
    _db.session.commit()
    return c


def login_as(client, username, password='userpass'):
    """Log in via the /login form and follow the redirect."""
    return client.post(
        '/login',
        data={'username': username, 'password': password},
        follow_redirects=True,
    )
