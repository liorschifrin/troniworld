"""Tests for /admin/users user management routes."""
from werkzeug.security import check_password_hash
from flask_app import db
from flask_app.models import User, Player
from tests.conftest import make_admin, make_user, login_as


# ── Access control ────────────────────────────────────────────────────────────

def test_manage_users_get_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/admin/users', follow_redirects=False)
    assert rv.status_code == 302


def test_manage_users_get_admin_200(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/admin/users')
    assert rv.status_code == 200


# ── Create user ───────────────────────────────────────────────────────────────

def test_create_user_action(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'newguy', 'is_admin': '', 'is_leadership': ''},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    user = User.query.filter_by(username='Newguy').first()
    assert user is not None
    assert not user.is_admin
    assert not user.is_leadership


def test_create_user_uses_user_shared_password(client):
    """New non-admin user is created with the hashed user password."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'testmember', 'is_admin': '', 'is_leadership': ''},
    )
    user = User.query.filter_by(username='Testmember').first()
    assert user is not None
    # The stored hash should match the shared user password (lowercased)
    assert check_password_hash(user.hashed_password, 'userpass')


def test_create_admin_user_uses_admin_password(client):
    """New admin user is created with the hashed admin password."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'newadmin', 'is_admin': 'on', 'is_leadership': ''},
    )
    user = User.query.filter_by(username='Newadmin').first()
    assert user is not None
    assert user.is_admin
    assert check_password_hash(user.hashed_password, 'adminpass')


def test_create_user_duplicate_username_flashes_error(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    # First create
    client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'alice', 'is_admin': '', 'is_leadership': ''},
    )
    # Duplicate
    rv = client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'ALICE', 'is_admin': '', 'is_leadership': ''},
        follow_redirects=True,
    )
    assert b'already exists' in rv.data
    assert User.query.filter_by(is_admin=False).count() == 1


def test_create_user_with_valid_player_name(client):
    """Creating a user with a valid player_name links them."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    player = Player(name='Jordan')
    db.session.add(player)
    db.session.commit()

    client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'jordan', 'is_admin': '', 'is_leadership': '', 'player_name': 'Jordan'},
    )
    user = User.query.filter_by(username='Jordan').first()
    assert user is not None
    assert user.player_id == player.id


def test_create_user_with_invalid_player_name_flashes_error(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/admin/users',
        data={'action': 'create', 'username': 'someone', 'is_admin': '', 'is_leadership': '', 'player_name': 'NoSuchPlayer'},
        follow_redirects=True,
    )
    assert b'not found' in rv.data


# ── Delete user ───────────────────────────────────────────────────────────────

def test_delete_user_action(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    target = make_user('Bob')
    rv = client.post(
        '/admin/users',
        data={'action': 'delete', 'user_id': str(target.id)},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert db.session.get(User, target.id) is None


def test_delete_self_flashes_error(client):
    """Admin cannot delete their own account."""
    admin = make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/admin/users',
        data={'action': 'delete', 'user_id': str(admin.id)},
        follow_redirects=True,
    )
    assert b'cannot delete your own' in rv.data
    assert db.session.get(User, admin.id) is not None


# ── Toggle role ───────────────────────────────────────────────────────────────

def test_toggle_admin_role(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    target = make_user('Bob')

    rv = client.post(
        '/admin/users',
        data={'action': 'toggle_role', 'user_id': str(target.id), 'role_type': 'admin'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    db.session.refresh(target)
    assert target.is_admin is True


def test_toggle_admin_updates_password(client):
    """Toggling admin on should update the user's password hash to admin password."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    target = make_user('Bob')

    client.post(
        '/admin/users',
        data={'action': 'toggle_role', 'user_id': str(target.id), 'role_type': 'admin'},
    )
    db.session.refresh(target)
    assert check_password_hash(target.hashed_password, 'adminpass')


def test_toggle_leadership_role(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    target = make_user('Carol')

    client.post(
        '/admin/users',
        data={'action': 'toggle_role', 'user_id': str(target.id), 'role_type': 'leadership'},
    )
    db.session.refresh(target)
    assert target.is_leadership is True


def test_toggle_role_ajax_returns_json(client):
    """AJAX toggle_role (X-Requested-With header) returns JSON."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    target = make_user('Dan')

    rv = client.post(
        '/admin/users',
        data={'action': 'toggle_role', 'user_id': str(target.id), 'role_type': 'leadership'},
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    assert 'new_value' in data


# ── Bulk create players ───────────────────────────────────────────────────────

def test_create_all_players_creates_users(client):
    """Bulk-create creates a User for each Player that doesn't have one."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    p1 = Player(name='Taylor')
    p2 = Player(name='Morgan')
    db.session.add_all([p1, p2])
    db.session.commit()

    rv = client.post('/admin/users/create_all_players', follow_redirects=False)
    assert rv.status_code == 302

    assert User.query.filter_by(username='Taylor').first() is not None
    assert User.query.filter_by(username='Morgan').first() is not None


def test_create_all_players_skips_existing_users(client):
    """Players that already have an associated user are skipped."""
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    p = Player(name='Existing')
    db.session.add(p)
    db.session.flush()
    # Pre-create the user linked to this player
    u = User(username='Existing', hashed_password='x', is_admin=False, player_id=p.id)
    db.session.add(u)
    db.session.commit()

    client.post('/admin/users/create_all_players')
    # Should still be exactly one user named Existing
    assert User.query.filter_by(username='Existing').count() == 1
