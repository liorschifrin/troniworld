"""Tests for film room page routes (status codes and redirect behavior)."""
from flask_app import db
from flask_app.models import Game, Tournament
from tests.conftest import make_admin, make_user, make_game, login_as


# ── Unauthenticated → redirect to login ──────────────────────────────────────

def test_games_list_unauthenticated(client):
    rv = client.get('/film/games', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_my_games_unauthenticated(client):
    rv = client.get('/film/my-games', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_tron_data_unauthenticated(client):
    rv = client.get('/film/data', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_analytics_unauthenticated(client):
    rv = client.get('/film/analytics', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


# ── Games list ────────────────────────────────────────────────────────────────

def test_games_list_200_as_user(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/games')
    assert rv.status_code == 200


def test_games_list_200_as_admin(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/games')
    assert rv.status_code == 200


# ── Game player ───────────────────────────────────────────────────────────────

def test_view_game_200(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    rv = client.get(f'/film/games/{g.id}')
    assert rv.status_code == 200


def test_view_hidden_game_accessible_when_direct_link(client):
    """Hidden games are still accessible via direct URL to any logged-in user.
    The is_hidden flag only hides games from the games list, not the player page."""
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game(is_hidden=True)
    rv = client.get(f'/film/games/{g.id}')
    assert rv.status_code == 200


def test_view_hidden_game_as_admin_returns_200(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    g = make_game(is_hidden=True)
    rv = client.get(f'/film/games/{g.id}')
    assert rv.status_code == 200


def test_view_nonexistent_game_returns_404(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/games/99999')
    assert rv.status_code == 404


# ── New game ──────────────────────────────────────────────────────────────────

def test_new_game_get_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/games/new', follow_redirects=False)
    assert rv.status_code == 302


def test_new_game_get_admin_200(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/games/new')
    assert rv.status_code == 200


def test_new_game_post_creates_game(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/film/games/new',
        data={'title': 'New Game', 'opponent': 'Rival FC', 'youtube_id': ''},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert Game.query.filter_by(title='New Game').first() is not None


# ── My games ──────────────────────────────────────────────────────────────────

def test_my_games_200(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/my-games')
    assert rv.status_code == 200


# ── Tron data ─────────────────────────────────────────────────────────────────

def test_tron_data_200(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/data')
    assert rv.status_code == 200


# ── Analytics ─────────────────────────────────────────────────────────────────

def test_analytics_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/analytics', follow_redirects=False)
    assert rv.status_code == 302


def test_analytics_admin_200(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/analytics')
    assert rv.status_code == 200


# ── New tournament ────────────────────────────────────────────────────────────

def test_new_tournament_post_creates_tournament(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/film/tournaments/new',
        data={'name': 'Spring Open', 'start_date': '2024-04-01'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert Tournament.query.filter_by(name='Spring Open').first() is not None


# ── Delete player sheet ───────────────────────────────────────────────────────

def test_delete_player_sheet_clears_data(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    g = make_game()
    g.player_order_data = {'players': ['Alice', 'Bob'], 'separator_index': 1}
    db.session.commit()

    rv = client.post(f'/film/games/{g.id}/delete_player_sheet', follow_redirects=False)
    assert rv.status_code == 302
    db.session.refresh(g)
    assert g.player_order_data is None
