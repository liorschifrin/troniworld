"""Tests for film room JSON/AJAX endpoints."""
import json
from flask_app import db
from flask_app.models import (
    Comment, CommentNotification, GameWatched, VideoWatchSession
)
from tests.conftest import (
    make_admin, make_user, make_leadership, make_game, make_point,
    make_comment, login_as
)


# ── Get comments ─────────────────────────────────────────────────────────────

def test_get_comments_unauthenticated(client):
    g = make_game()
    rv = client.get(f'/film/api/games/{g.id}/comments', follow_redirects=False)
    assert rv.status_code == 302
    assert '/login' in rv.headers['Location']


def test_get_comments_returns_public_comments(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    make_comment(g.id, author_name='Alice', content='Public comment')

    rv = client.get(f'/film/api/games/{g.id}/comments')
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data['comments']) == 1
    assert data['comments'][0]['content'] == 'Public comment'


def test_get_comments_excludes_private_from_non_recipients(client):
    """A private comment should not be visible to users not in private_to."""
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    # Alice sends a private comment to herself only
    make_comment(g.id, author_name='Alice', content='Secret', private_to=['Alice'])

    rv = client.get(f'/film/api/games/{g.id}/comments')
    data = rv.get_json()
    assert len(data['comments']) == 0


def test_get_comments_private_recipient_sees_comment(client):
    """The intended recipient of a private comment can see it."""
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    make_comment(g.id, author_name='Alice', content='For Bob', private_to=['Bob'])

    rv = client.get(f'/film/api/games/{g.id}/comments')
    data = rv.get_json()
    assert len(data['comments']) == 1
    assert data['comments'][0]['content'] == 'For Bob'


def test_get_comments_leadership_sees_leadership_private(client):
    """Leadership user can see private comments written by other leadership members."""
    make_leadership('Lead1')
    make_leadership('Lead2')
    login_as(client, 'Lead2', 'adminpass')
    g = make_game()
    make_comment(g.id, author_name='Lead1', content='Leadership only', private_to=['SomeoneElse'])

    rv = client.get(f'/film/api/games/{g.id}/comments')
    data = rv.get_json()
    assert len(data['comments']) == 1


# ── Create comment ────────────────────────────────────────────────────────────

def test_create_comment_returns_201(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Hello!', 'comment_type': 'Comment'},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data['comment']['author_name'] == 'Alice'
    assert data['comment']['content'] == 'Hello!'


def test_create_comment_empty_content_returns_400(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': ''},
    )
    assert rv.status_code == 400


def test_create_private_comment_creates_private_notifications(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Private', 'private_to': ['Bob']},
    )
    assert rv.status_code == 201
    notif = CommentNotification.query.filter_by(
        recipient_username='Bob', notification_type='private'
    ).first()
    assert notif is not None


def test_mention_creates_mention_notification(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Hey @[Bob] check this out'},
    )
    assert rv.status_code == 201
    notif = CommentNotification.query.filter_by(
        recipient_username='Bob', notification_type='mention'
    ).first()
    assert notif is not None


def test_everyone_mention_non_leadership_no_everyone_notif(client):
    """@[Everyone] mention by a non-leadership user does NOT create everyone notifications."""
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Hey @[Everyone] listen up'},
    )
    assert rv.status_code == 201
    count = CommentNotification.query.filter_by(notification_type='everyone').count()
    assert count == 0


def test_everyone_mention_leadership_creates_everyone_notifs(client):
    """@[Everyone] by a leadership user notifies all users except the author."""
    make_leadership('Lead')
    make_user('Bob')
    make_user('Carol')
    login_as(client, 'Lead', 'adminpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Hey @[Everyone] team meeting'},
    )
    assert rv.status_code == 201
    # Bob and Carol should get 'everyone' notifications; Lead (author) should not
    bob_notif = CommentNotification.query.filter_by(
        recipient_username='Bob', notification_type='everyone'
    ).first()
    lead_notif = CommentNotification.query.filter_by(
        recipient_username='Lead', notification_type='everyone'
    ).first()
    assert bob_notif is not None
    assert lead_notif is None


def test_reply_creates_reply_notification_for_parent_author(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    parent = make_comment(g.id, author_name='Alice', content='Parent')

    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Reply', 'parent_id': parent.id},
    )
    assert rv.status_code == 201
    notif = CommentNotification.query.filter_by(
        recipient_username='Alice', notification_type='reply'
    ).first()
    assert notif is not None


def test_reply_creates_thread_notification_for_other_participants(client):
    make_user('Alice')
    make_user('Bob')
    make_user('Carol')
    g = make_game()
    parent = make_comment(g.id, author_name='Alice', content='Parent')
    # Bob already replied
    make_comment(g.id, author_name='Bob', content='Bob reply', parent_id=parent.id)

    login_as(client, 'Carol', 'userpass')
    rv = client.post(
        f'/film/api/games/{g.id}/comments',
        json={'content': 'Carol reply', 'parent_id': parent.id},
    )
    assert rv.status_code == 201
    bob_notif = CommentNotification.query.filter_by(
        recipient_username='Bob', notification_type='thread'
    ).first()
    assert bob_notif is not None


# ── Update comment ────────────────────────────────────────────────────────────

def test_update_comment_by_author(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice', content='Original')

    rv = client.patch(
        f'/film/api/games/{g.id}/comments/{c.id}',
        json={'content': 'Updated'},
    )
    assert rv.status_code == 200
    db.session.refresh(c)
    assert c.content == 'Updated'


def test_update_comment_by_non_author_forbidden(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice', content='Original')

    rv = client.patch(
        f'/film/api/games/{g.id}/comments/{c.id}',
        json={'content': 'Hijacked'},
    )
    assert rv.status_code == 403


# ── Delete comment ────────────────────────────────────────────────────────────

def test_delete_comment_by_author(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')

    rv = client.delete(f'/film/api/games/{g.id}/comments/{c.id}')
    assert rv.status_code == 200
    assert db.session.get(Comment, c.id) is None


def test_delete_comment_by_admin_succeeds(client):
    """Admin can delete any comment."""
    make_admin()
    make_user('Alice')
    login_as(client, 'Admin', 'adminpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')

    rv = client.delete(f'/film/api/games/{g.id}/comments/{c.id}')
    assert rv.status_code == 200


def test_delete_comment_by_non_author_forbidden(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Bob', 'userpass')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')

    rv = client.delete(f'/film/api/games/{g.id}/comments/{c.id}')
    assert rv.status_code == 403


# ── Update point ──────────────────────────────────────────────────────────────

def test_update_point_non_admin_forbidden(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    p = make_point(g.id)

    rv = client.patch(
        f'/film/api/games/{g.id}/points/{p.id}',
        json={'pull_play': 'Force'},
    )
    assert rv.status_code == 302  # redirected to index (not admin)


def test_update_point_as_admin(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    g = make_game()
    p = make_point(g.id)

    rv = client.patch(
        f'/film/api/games/{g.id}/points/{p.id}',
        json={'pull_play': 'Force', 'defense_type': 'Vert'},
    )
    assert rv.status_code == 200
    db.session.refresh(p)
    assert p.pull_play == 'Force'
    assert p.defense_type == 'Vert'


# ── Watch tracking ────────────────────────────────────────────────────────────

def test_track_watch_time_creates_session(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(
        f'/film/api/games/{g.id}/track-watch-time',
        json={'seconds_watched': 60, 'playback_position': 120.5},
    )
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['success'] is True
    assert 'session_id' in data


def test_track_watch_time_updates_existing_session(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    # First call
    rv1 = client.post(
        f'/film/api/games/{g.id}/track-watch-time',
        json={'seconds_watched': 30, 'playback_position': 30.0},
    )
    session_id = rv1.get_json()['session_id']

    # Second call with session_id
    rv2 = client.post(
        f'/film/api/games/{g.id}/track-watch-time',
        json={'seconds_watched': 30, 'playback_position': 60.0, 'session_id': session_id},
    )
    assert rv2.status_code == 200
    assert rv2.get_json()['total_watched'] == 60


def test_get_watch_progress_no_session_returns_null(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.get(f'/film/api/games/{g.id}/watch-progress')
    assert rv.status_code == 200
    assert rv.get_json()['last_position'] is None


def test_get_watch_progress_position_below_30_returns_null(client, app):
    make_user('Alice')
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    from flask_app.models import User
    alice = User.query.filter_by(username='Alice').first()
    ws = VideoWatchSession(user_id=alice.id, game_id=g.id,
                           watch_duration_seconds=20, last_position_seconds=25.0)
    db.session.add(ws)
    db.session.commit()

    rv = client.get(f'/film/api/games/{g.id}/watch-progress')
    assert rv.get_json()['last_position'] is None


def test_get_watch_progress_position_above_30_returned(client):
    make_user('Alice')
    login_as(client, 'Alice', 'userpass')
    g = make_game()
    from flask_app.models import User
    alice = User.query.filter_by(username='Alice').first()
    ws = VideoWatchSession(user_id=alice.id, game_id=g.id,
                           watch_duration_seconds=200, last_position_seconds=350.0)
    db.session.add(ws)
    db.session.commit()

    rv = client.get(f'/film/api/games/{g.id}/watch-progress')
    assert rv.get_json()['last_position'] == 350.0


# ── Notifications ─────────────────────────────────────────────────────────────

def test_get_notifications_unauthenticated(client):
    rv = client.get('/film/api/notifications', follow_redirects=False)
    assert rv.status_code == 302


def test_get_notifications_returns_data(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/api/notifications')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'notifications' in data
    assert 'unread_count' in data


def test_mark_notification_read(client):
    make_user('Alice')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')
    notif = CommentNotification(
        recipient_username='Alice',
        comment_id=c.id,
        game_id=g.id,
        notification_type='mention',
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()

    login_as(client, 'Alice', 'userpass')
    rv = client.post(f'/film/api/notifications/{notif.id}/read')
    assert rv.status_code == 200
    db.session.refresh(notif)
    assert notif.is_read is True
    assert notif.read_at is not None


def test_mark_all_notifications_read(client):
    make_user('Alice')
    g = make_game()
    c = make_comment(g.id, author_name='Alice')
    for _ in range(3):
        db.session.add(CommentNotification(
            recipient_username='Alice',
            comment_id=c.id,
            game_id=g.id,
            notification_type='mention',
            is_read=False,
        ))
    db.session.commit()

    login_as(client, 'Alice', 'userpass')
    rv = client.post('/film/api/notifications/read-all')
    assert rv.status_code == 200
    unread = CommentNotification.query.filter_by(
        recipient_username='Alice', is_read=False
    ).count()
    assert unread == 0


# ── Toggle watched ────────────────────────────────────────────────────────────

def test_toggle_watched_creates_record(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    rv = client.post(f'/film/api/games/{g.id}/toggle-watched')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['watched'] is True
    assert GameWatched.query.filter_by(game_id=g.id).count() == 1


def test_toggle_watched_second_call_removes_record(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    g = make_game()

    client.post(f'/film/api/games/{g.id}/toggle-watched')  # mark watched
    rv = client.post(f'/film/api/games/{g.id}/toggle-watched')  # unmark
    assert rv.status_code == 200
    assert rv.get_json()['watched'] is False
    assert GameWatched.query.filter_by(game_id=g.id).count() == 0


# ── User watched games (admin) ────────────────────────────────────────────────

def test_get_user_watched_games_as_admin(client):
    make_admin()
    make_user('Bob')
    login_as(client, 'Admin', 'adminpass')
    rv = client.get('/film/api/user/Bob/watched-games')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'watched_games' in data


def test_get_user_watched_games_as_non_admin_forbidden(client):
    make_user('Alice')
    make_user('Bob')
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/film/api/user/Bob/watched-games', follow_redirects=False)
    assert rv.status_code == 302  # redirected to index
