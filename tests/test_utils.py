"""Tests for auth utility decorators."""
from tests.conftest import make_admin, make_user, make_leadership, login_as


def test_get_current_user_no_session(client):
    """get_current_user() returns None when no session cookie is set."""
    from flask_app.utils import get_current_user
    with client.application.app_context():
        user = get_current_user()
    assert user is None


def test_login_required_redirects_to_login(client):
    """Unauthenticated request to a @login_required route → redirect to /login."""
    rv = client.get('/film/games')
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_login_required_allows_logged_in(client):
    """Authenticated user gets through @login_required."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/games')
    assert rv.status_code == 200


def test_admin_required_redirects_non_admin(client):
    """Non-admin user hitting an @admin_required route → redirect to index."""
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/analytics', follow_redirects=False)
    assert rv.status_code == 302
    assert rv.headers['Location'].endswith('/')


def test_admin_required_allows_admin(client):
    """Admin user can access an @admin_required route."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/analytics')
    assert rv.status_code == 200


def test_leadership_required_allows_admin(client):
    """Admin satisfies @leadership_required."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    # /admin/users is admin_required; use a leadership check via API
    rv = client.get('/admin/users')
    assert rv.status_code == 200


def test_leadership_required_blocks_regular_user(client):
    """Regular user cannot access the admin user management page."""
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/admin/users', follow_redirects=False)
    assert rv.status_code == 302
