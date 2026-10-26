"""T09: trustworthy engagement and notification state (synthetic data only)."""
import json
from datetime import datetime, timedelta

import pytest

from flask_app import watch_time


def track(client, game, **body):
    return client.post(f'/film/api/games/{game.id}/track-watch-time', json=body)


def chunk(session='tab-a', n=1, seconds=10, **extra):
    return dict(client_session_id=session, event_id=f'{session}:{n}', seconds_watched=seconds, **extra)


def sessions(db, user=None):
    from flask_app.models import VideoWatchSession
    query = VideoWatchSession.query
    if user is not None:
        query = query.filter_by(user_id=user.id)
    return query.order_by(VideoWatchSession.id).all()


def events(db):
    from flask_app.models import VideoWatchEvent
    return VideoWatchEvent.query.all()


# ---- 1. accepted media type -------------------------------------------------

def test_json_blob_beacon_is_accepted(ordinary, records, db):
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=json.dumps(dict(chunk(), csrf_token='synthetic-csrf-ordinary')),
                             content_type='application/json')
    assert response.status_code == 200 and response.json['success'] is True
    assert sessions(db)[0].watch_duration_seconds == 10


def test_text_plain_beacon_from_an_older_page_still_parses(ordinary, records, db):
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=json.dumps(chunk()), content_type='text/plain;charset=UTF-8')
    assert response.status_code == 200 and sessions(db)[0].watch_duration_seconds == 10


@pytest.mark.parametrize('body', ['not json', '[1, 2]', '"text"', 'null', ''])
def test_unparseable_bodies_get_400_json_without_writes(ordinary, records, db, body):
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=body, content_type='text/plain')
    assert response.status_code == 400 and response.is_json
    assert sessions(db) == [] and events(db) == []


def test_template_sends_a_json_blob_and_gates_on_visible_focused_playback():
    from pathlib import Path
    source = (Path(watch_time.__file__).parent / 'templates/film_room/pages/game_player.html').read_text()
    assert "new Blob([data], { type: 'application/json' })" in source
    assert "state === YT.PlayerState.PLAYING && watchTabActive()" in source
    assert "document.visibilityState === 'visible' && document.hasFocus()" in source
    assert "addEventListener('pagehide'" in source and "addEventListener('beforeunload'" in source


# ---- 2. idempotent increments ------------------------------------------------

def test_replayed_event_is_acknowledged_but_counted_once(ordinary, records, db):
    first = track(ordinary, records['game'], **chunk(seconds=10))
    replay = track(ordinary, records['game'], **chunk(seconds=10))
    assert first.json['duplicate'] is False and first.json['credited'] == 10
    assert replay.status_code == 200 and replay.json['duplicate'] is True and replay.json['credited'] == 0
    assert replay.json['session_id'] == first.json['session_id']
    assert sessions(db)[0].watch_duration_seconds == 10 and len(events(db)) == 1


def test_replay_with_a_different_amount_does_not_change_the_total(ordinary, records, db):
    track(ordinary, records['game'], **chunk(seconds=10))
    track(ordinary, records['game'], **chunk(seconds=50))
    assert sessions(db)[0].watch_duration_seconds == 10


def test_late_and_out_of_order_events_are_all_counted_once(ordinary, records, db):
    for n in (3, 1, 2, 3, 1):
        track(ordinary, records['game'], **chunk(n=n, seconds=7))
    assert len(sessions(db)) == 1
    assert sessions(db)[0].watch_duration_seconds == 21 and len(events(db)) == 3


def test_fractional_chunks_do_not_lose_time_to_rounding(ordinary, records, db):
    for n in range(1, 5):
        track(ordinary, records['game'], **chunk(n=n, seconds=10.4))
    assert sessions(db)[0].watch_duration_seconds == 42  # 41.6 rounded once, not 4 x 10


def test_position_only_update_needs_no_event_and_adds_no_time(ordinary, records, db):
    response = track(ordinary, records['game'], client_session_id='tab-a', playback_position=65)
    assert response.status_code == 200 and response.json['credited'] == 0
    assert sessions(db)[0].last_position_seconds == 65 and events(db) == []
    assert ordinary.get(f'/film/api/games/{records["game"].id}/watch-progress').json == {'last_position': 65}


def test_seconds_without_event_id_are_refused(ordinary, records, db):
    response = track(ordinary, records['game'], client_session_id='tab-a', seconds_watched=10)
    assert response.status_code == 400 and sessions(db) == []


def test_legacy_rows_are_preserved_and_never_extended(ordinary, records, db):
    from flask_app.models import VideoWatchSession
    legacy = VideoWatchSession(user_id=records['users']['ordinary'].id, game_id=records['game'].id,
                               watch_duration_seconds=300)
    db.session.add(legacy)
    db.session.commit()
    response = track(ordinary, records['game'], session_id=legacy.id, **chunk(seconds=5))
    assert response.json['session_id'] != legacy.id
    db.session.refresh(legacy)
    assert legacy.watch_duration_seconds == 300 and legacy.client_session_id is None


# ---- 3. bounded durations, user-scoped sessions -----------------------------

def test_single_increment_is_capped(ordinary, records, db):
    response = track(ordinary, records['game'], **chunk(seconds=10 ** 9))
    assert response.status_code == 200
    assert response.json['credited'] == watch_time.MAX_INCREMENT_SECONDS == 60


def test_single_increment_cap_applies_to_an_old_session(app, records, db):
    user, game = records['users']['ordinary'], records['game']
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    watch_time.record(user.id, game.id, chunk(seconds=1), now=t0)
    _, credited, _ = watch_time.record(user.id, game.id, chunk(n=2, seconds=10 ** 9), now=t0 + timedelta(hours=1))
    assert credited == watch_time.MAX_INCREMENT_SECONDS


def test_a_flood_of_max_chunks_cannot_exceed_session_age_plus_one_chunk(ordinary, records, db):
    for n in range(1, 21):
        track(ordinary, records['game'], **chunk(n=n, seconds=60))
    assert sessions(db)[0].watch_duration_seconds <= 61


@pytest.mark.parametrize('seconds', [-1, -0.001, True, False, '10', None, [10], {'a': 1}, 1e999])
def test_invalid_durations_are_refused_without_writes(ordinary, records, db, seconds):
    body = json.dumps(dict(chunk(), seconds_watched=seconds), allow_nan=True)
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=body, content_type='application/json')
    assert response.status_code == 400 and response.is_json
    assert sessions(db) == [] and events(db) == []


@pytest.mark.parametrize('literal', ['NaN', 'Infinity', '-Infinity'])
def test_non_finite_durations_are_refused(ordinary, records, db, literal):
    body = '{"client_session_id": "t", "event_id": "t:1", "seconds_watched": %s}' % literal
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=body, content_type='application/json')
    assert response.status_code == 400 and sessions(db) == []


@pytest.mark.parametrize('field,value', [
    ('client_session_id', ''), ('client_session_id', 'x' * 65), ('client_session_id', 7),
    ('client_session_id', None), ('event_id', ''), ('event_id', 'x' * 65), ('event_id', ['a']),
    ('playback_position', -1), ('playback_position', 86401), ('playback_position', 'soon'),
    ('playback_position', True)])
def test_invalid_identifiers_and_positions_are_refused(ordinary, records, db, field, value):
    response = track(ordinary, records['game'], **dict(chunk(), **{field: value}))
    assert response.status_code == 400 and sessions(db) == [] and events(db) == []


def test_users_cannot_write_into_each_others_sessions(ordinary, admin, records, db):
    first = track(admin, records['game'], **chunk(seconds=10))
    second = track(ordinary, records['game'], session_id=first.json['session_id'], **chunk(seconds=20))
    assert second.json['session_id'] != first.json['session_id'] and second.json['duplicate'] is False
    by_user = {s.user_id: s.watch_duration_seconds for s in sessions(db)}
    assert by_user == {records['users']['admin'].id: 10, records['users']['ordinary'].id: 20}


def test_session_lookup_is_per_game(ordinary, records, db):
    track(ordinary, records['game'], **chunk(seconds=10))
    # hidden game is invisible to ordinary users
    assert track(ordinary, records['hidden'], **chunk(n=2, seconds=10)).status_code == 404
    assert [s.watch_duration_seconds for s in sessions(db)] == [10]


# ---- tabs --------------------------------------------------------------------

def test_overlapping_tabs_do_not_add_extra_time(app, records, db):
    user, game = records['users']['ordinary'], records['game']
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    watch_time.record(user.id, game.id, chunk('tab-a', 1, 10), now=t0)
    # Tab B reports 10s ending 4s after tab A's chunk ended: 6s of it were already credited.
    _, credited, _ = watch_time.record(user.id, game.id, chunk('tab-b', 1, 10), now=t0 + timedelta(seconds=4))
    assert credited == pytest.approx(4)
    # Later, separate time in either tab is credited in full.
    _, credited, _ = watch_time.record(user.id, game.id, chunk('tab-b', 2, 10), now=t0 + timedelta(seconds=30))
    assert credited == pytest.approx(10)
    total = sum(s.watch_duration_seconds for s in sessions(db))
    assert total == 24


def test_consecutive_chunks_of_one_tab_are_never_trimmed(app, records, db):
    user, game = records['users']['ordinary'], records['game']
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    for n in range(1, 6):  # arrivals jitter earlier than the chunk length
        _, credited, _ = watch_time.record(user.id, game.id, chunk('tab-a', n, 10),
                                           now=t0 + timedelta(seconds=9.9 * n))
        assert credited == 10


def test_another_users_time_never_trims_mine(app, records, db):
    game = records['game']
    t0 = datetime(2026, 1, 1, 12, 0, 0)
    watch_time.record(records['users']['admin'].id, game.id, chunk('tab-a', 1, 10), now=t0)
    _, credited, _ = watch_time.record(records['users']['ordinary'].id, game.id, chunk('tab-a', 1, 10), now=t0)
    assert credited == 10


# ---- 4. notification read state survives harmless edits ---------------------

def make_mention(admin, records, text='Hello @[recipient]'):
    response = admin.post(f'/film/api/games/{records["game"].id}/comments', json={'content': text})
    assert response.status_code == 201
    return response.json['comment']['id']


def notification_rows(username='recipient'):
    from flask_app.models import CommentNotification
    return CommentNotification.query.filter_by(recipient_username=username).order_by(CommentNotification.id).all()


def test_edit_that_keeps_recipients_keeps_read_state(admin, client_for, records, db):
    comment_id = make_mention(admin, records)
    recipient = client_for('recipient')
    (row,) = notification_rows()
    assert recipient.post(f'/film/api/notifications/{row.id}/read').status_code == 200
    db.session.expire_all()
    read_at = notification_rows()[0].read_at
    assert read_at is not None

    edited = admin.patch(f'/film/api/games/{records["game"].id}/comments/{comment_id}',
                         json={'content': 'Fixed typo for @[recipient]'})
    assert edited.status_code == 200
    db.session.expire_all()
    (after,) = notification_rows()
    assert (after.id, after.is_read, after.read_at) == (row.id, True, read_at)
    assert recipient.get('/film/api/notifications').json['unread_count'] == 0


def test_edit_that_adds_a_recipient_notifies_only_the_new_one(admin, client_for, records, db):
    from flask_app.models import User
    db.session.add(User(username='newcomer', hashed_password='synthetic-unused-hash'))
    db.session.commit()
    comment_id = make_mention(admin, records)
    (row,) = notification_rows()
    client_for('recipient').post(f'/film/api/notifications/{row.id}/read')
    admin.patch(f'/film/api/games/{records["game"].id}/comments/{comment_id}',
                json={'content': 'Hello @[recipient] and @[newcomer]'})
    db.session.expire_all()
    assert [(n.id, n.is_read) for n in notification_rows()] == [(row.id, True)]
    assert [n.is_read for n in notification_rows('newcomer')] == [False]


# ---- 5. unread count includes older rows ------------------------------------

def seed_notifications(db, records, count, *, read=0):
    from flask_app.models import Comment, CommentNotification
    base = datetime(2026, 1, 1)
    ids = []
    for i in range(count):
        comment = Comment(game_id=records['game'].id, author_name='admin', content=f'Synthetic {i}',
                          comment_type='Comment')
        db.session.add(comment)
        db.session.flush()
        row = CommentNotification(recipient_username='recipient', comment_id=comment.id,
                                  game_id=records['game'].id, notification_type='mention',
                                  is_read=i < read, created_at=base + timedelta(minutes=i))
        db.session.add(row)
        ids.append(row)
    db.session.commit()
    return ids


def test_unread_count_is_not_limited_to_the_newest_page(client_for, records, db):
    seed_notifications(db, records, 60)
    body = client_for('recipient').get('/film/api/notifications').json
    assert len(body['notifications']) == 50
    assert body['unread_count'] == 60


def test_unread_count_ignores_read_rows_and_older_unread_still_counts(client_for, records, db):
    # The 55 oldest are read, the 5 newest unread -> 5. Then the newest 50 are all read
    # while 10 older rows are not -> 10, though the list shows only read rows.
    rows = seed_notifications(db, records, 60, read=55)
    client = client_for('recipient')
    assert client.get('/film/api/notifications').json['unread_count'] == 5
    for index, row in enumerate(rows):
        row.is_read = index >= 10
    db.session.commit()
    body = client.get('/film/api/notifications').json
    assert body['unread_count'] == 10
    assert all(n['is_read'] for n in body['notifications'])


def test_unread_count_omits_rows_the_user_may_not_view(client_for, records, db):
    from flask_app.models import CommentNotification
    seed_notifications(db, records, 3)
    private = records['private']  # visible only to admin and "recipient"
    db.session.add(CommentNotification(recipient_username='ordinary', comment_id=private.id,
                                       game_id=records['game'].id, notification_type='private'))
    db.session.commit()
    body = client_for('ordinary').get('/film/api/notifications').json
    assert body['notifications'] == [] and body['unread_count'] == 0
    assert client_for('recipient').get('/film/api/notifications').json['unread_count'] == 3


# ---- 6. filtered statistics use one population -------------------------------

@pytest.fixture
def stats_context(monkeypatch, records, db):
    from flask_app.models import Game, Player, Point
    from flask_app import film_routes
    other = Game(title='Synthetic second game', opponent='Synthetic visitors')
    third = Game(title='Synthetic third game', opponent='Synthetic visitors')
    db.session.add_all([other, third])
    db.session.flush()
    player = Player(name='Synthetic Player', active=True)
    db.session.add(player)
    for game, index in ((records['game'], 2), (other, 1), (third, 1)):
        point = Point(game_id=game.id, point_index=index, tron_o=True, tron_point=True)
        db.session.add(point)
        point.players.append(player)
        game.roster.append(player)
    db.session.commit()
    captured = {}
    real = film_routes.render_template
    monkeypatch.setattr(film_routes, 'render_template',
                        lambda template, **context: captured.update(context) or real(template, **context))
    return dict(games=(records['game'], other, third), captured=captured, player=player)


def test_unfiltered_page_counts_every_visible_game(ordinary, stats_context):
    assert ordinary.get('/film/data').status_code == 200
    context = stats_context['captured']
    assert context['total_games'] == 3 and context['total_o_points'] == 3
    assert [s['games_played'] for s in context['player_stats']] == [3]


def test_filtered_game_count_matches_point_stats(ordinary, stats_context):
    first, second, _ = stats_context['games']
    assert ordinary.get(f'/film/data?game_ids={second.id}').status_code == 200
    context = stats_context['captured']
    (player_row,) = context['player_stats']
    assert context['total_games'] == 1 and context['total_o_points'] == 1
    assert (player_row['total_pts'], player_row['games_played']) == (1, 1)


def test_filter_with_two_games_and_a_hidden_id(ordinary, admin, records, stats_context):
    first, second, _ = stats_context['games']
    url = f'/film/data?game_ids={first.id}&game_ids={second.id}&game_ids={records["hidden"].id}'
    assert ordinary.get(url).status_code == 200
    context = stats_context['captured']
    assert context['total_games'] == 2 and context['total_o_points'] == 2
    assert [(s['total_pts'], s['games_played']) for s in context['player_stats']] == [(2, 2)]


def test_filter_naming_only_hidden_games_is_empty_for_ordinary_users(ordinary, records, stats_context):
    assert ordinary.get(f'/film/data?game_ids={records["hidden"].id}').status_code == 200
    context = stats_context['captured']
    assert context['total_games'] == 0 and context['total_o_points'] == 0 and context['player_stats'] == []
