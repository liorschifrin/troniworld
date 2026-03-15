"""Tests for /register, /login, /logout."""
import pytest
from flask_app import db
from flask_app.models import User, LoginEvent
from tests.conftest import make_admin, make_user, login_as


# ── Register ─────────────────────────────────────────────────────────────────

def test_register_get_no_admin(client):
    """GET /register renders when no admin exists yet."""
    rv = client.get('/register')
    assert rv.status_code == 200


def test_register_get_redirects_when_admin_exists(client):
    """GET /register with existing admin and no session → redirect to /login."""
    make_admin()
    rv = client.get('/register', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_register_post_creates_user(client):
    """POST /register creates a user and sets the session."""
    rv = client.post(
        '/register',
        data={'username': 'newuser', 'is_admin': '0'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    user = User.query.filter_by(username='Newuser').first()
    assert user is not None
    assert not user.is_admin


def test_register_post_creates_admin(client):
    """POST /register with is_admin=1 creates an admin user."""
    rv = client.post(
        '/register',
        data={'username': 'firstadmin', 'is_admin': '1'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    user = User.query.filter_by(username='Firstadmin').first()
    assert user is not None
    assert user.is_admin


def test_register_post_sets_session(client):
    """After registering, the session user_id is set."""
    with client:
        client.post(
            '/register',
            data={'username': 'bob', 'is_admin': '0'},
        )
        with client.session_transaction() as sess:
            assert 'user_id' in sess


def test_register_duplicate_username(client):
    """Registering with an existing username (case-insensitive) shows an error."""
    client.post('/register', data={'username': 'alice', 'is_admin': '0'})
    rv = client.post(
        '/register',
        data={'username': 'ALICE', 'is_admin': '0'},
        follow_redirects=True,
    )
    assert b'already exists' in rv.data


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success_sets_session(client):
    """Successful login stores user_id in the session."""
    make_user()
    with client:
        login_as(client, 'Alice', 'userpass')
        with client.session_transaction() as sess:
            assert 'user_id' in sess


def test_login_creates_login_event(client):
    """Successful login creates a LoginEvent record."""
    user = make_user()
    login_as(client, 'Alice', 'userpass')
    event = LoginEvent.query.filter_by(user_id=user.id).first()
    assert event is not None


def test_login_wrong_password(client):
    """Wrong password → no session set, flash message shown."""
    make_user()
    with client:
        rv = client.post(
            '/login',
            data={'username': 'Alice', 'password': 'wrongpass'},
            follow_redirects=True,
        )
        assert b'Invalid' in rv.data
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


def test_login_unknown_username(client):
    """Unknown username → flash, no session."""
    with client:
        rv = client.post(
            '/login',
            data={'username': 'nobody', 'password': 'userpass'},
            follow_redirects=True,
        )
        assert b'Invalid' in rv.data
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


def test_login_case_insensitive_username(client):
    """Login username match is case-insensitive."""
    make_user('alice')
    with client:
        login_as(client, 'ALICE', 'userpass')
        with client.session_transaction() as sess:
            assert 'user_id' in sess


def test_login_with_next_param_redirects(client):
    """Login with ?next=/film/games redirects there after success."""
    make_admin()
    rv = client.post(
        '/login?next=/film/games',
        data={'username': 'Admin', 'password': 'adminpass'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert '/film/games' in rv.headers['Location']


def test_login_admin_uses_admin_password(client):
    """Admin user must submit the admin password."""
    make_admin()
    with client:
        rv = client.post(
            '/login',
            data={'username': 'Admin', 'password': 'userpass'},  # wrong password
            follow_redirects=True,
        )
        assert b'Invalid' in rv.data
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout_clears_session(client):
    """GET /logout removes user_id from session."""
    make_user()
    with client:
        login_as(client, 'Alice', 'userpass')
        client.get('/logout')
        with client.session_transaction() as sess:
            assert 'user_id' not in sess


def test_logout_redirects_to_index(client):
    """Logout redirects to the index page."""
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/logout', follow_redirects=False)
    assert rv.status_code == 302
    assert rv.headers['Location'].endswith('/')
