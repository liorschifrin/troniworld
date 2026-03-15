"""Tests for the /api/v1/ REST Blueprint."""
from flask_app import db
from flask_app.models import Comment, Point
from tests.conftest import make_admin, make_user, make_game, make_point, make_comment, login_as


# ── Access control ────────────────────────────────────────────────────────────

def test_games_index_unauthenticated(client):
    rv = client.get('/api/v1/games', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


# ── Games index ───────────────────────────────────────────────────────────────

def test_games_index_returns_list(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    make_game('Alpha', 'Rival')
    make_game('Beta', 'Foes')

    rv = client.get('/api/v1/games')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'games' in data
    titles = [g['title'] for g in data['games']]
    assert 'Alpha' in titles
    assert 'Beta' in titles


def test_games_index_includes_expected_fields(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    make_game('Test', 'Opponent')

    data = client.get('/api/v1/games').get_json()
    game = data['games'][0]
    assert 'id' in game
    assert 'title' in game
    assert 'opponent' in game


# ── Game detail ───────────────────────────────────────────────────────────────

def test_game_detail_returns_game(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game('Detail Game', 'Rival')

    rv = client.get(f'/api/v1/games/{g.id}')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['game']['title'] == 'Detail Game'
    assert data['game']['opponent'] == 'Rival'


def test_game_detail_404_for_missing_game(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/api/v1/games/99999')
    assert rv.status_code == 404


def test_game_detail_includes_points_and_comments(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    make_point(g.id, point_index=1)
    make_comment(g.id, author_name='Alice', content='Nice play')

    data = client.get(f'/api/v1/games/{g.id}').get_json()
    assert len(data['game']['points']) == 1
    assert len(data['game']['comments']) == 1


# ── Game comments ─────────────────────────────────────────────────────────────

def test_game_comments_returns_list(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    make_comment(g.id, author_name='Alice', content='First')
    make_comment(g.id, author_name='Alice', content='Second')

    rv = client.get(f'/api/v1/games/{g.id}/comments')
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data['comments']) == 2


# ── Create comment ────────────────────────────────────────────────────────────

def test_create_game_comment_201(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/api/v1/games/{g.id}/comments',
        json={'content': 'Great cut!'},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data['comment']['content'] == 'Great cut!'
    assert data['comment']['author_name'] == 'Alice'


def test_create_game_comment_empty_content_400(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(f'/api/v1/games/{g.id}/comments', json={'content': ''})
    assert rv.status_code == 400


def test_create_game_comment_with_parent(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    parent = make_comment(g.id, author_name='Alice', content='Parent')

    rv = client.post(
        f'/api/v1/games/{g.id}/comments',
        json={'content': 'Reply', 'parent_id': parent.id},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data['comment']['parent_id'] == parent.id


# ── Update point ──────────────────────────────────────────────────────────────

def test_update_game_point_as_admin(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    g = make_game()
    p = make_point(g.id)

    rv = client.patch(
        f'/api/v1/games/{g.id}/points/{p.id}',
        json={'pull_play': 'Stack', 'defense_type': 'Vert'},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['point']['pull_play'] == 'Stack'
    assert data['point']['defense_type'] == 'Vert'


def test_update_game_point_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    p = make_point(g.id)

    rv = client.patch(
        f'/api/v1/games/{g.id}/points/{p.id}',
        json={'pull_play': 'Force'},
        follow_redirects=False,
    )
    assert rv.status_code == 302


# ── Delete comment ────────────────────────────────────────────────────────────

def test_delete_game_comment_by_author(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')

    rv = client.delete(f'/api/v1/games/{g.id}/comments/{c.id}')
    assert rv.status_code == 200
    assert db.session.get(Comment, c.id) is None


def test_delete_game_comment_non_author_forbidden(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')

    rv = client.delete(f'/api/v1/games/{g.id}/comments/{c.id}')
    assert rv.status_code == 403
