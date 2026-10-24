"""T03 visibility matrix; see docs/visibility-policy.md for the policy and roles."""
from urllib.parse import urlsplit

import pytest

MISSING_GAME = 10 ** 6
HIDDEN_TITLE = 'Synthetic hidden game'


@pytest.fixture
def scenario(records, db):
    """Comments covering every role in the matrix.

    author/recipient/leader_author/bystander are added to the role table so
    client_for() can sign them in; 'ordinary' doubles as a nonrecipient and
    'leadership' as a leadership nonrecipient.
    """
    from flask_app.models import Comment, CommentNotification, Player, User
    users = records['users']
    for name, leadership in (('author', False), ('leader_author', True), ('bystander', False)):
        users[name] = User(username=name, hashed_password='synthetic-unused-hash',
                           is_leadership=leadership)
    player = Player(name='Synthetic Player')
    users['ordinary'].player = player
    player.games.extend([records['game'], records['hidden']])
    db.session.add_all([users['author'], users['leader_author'], users['bystander'], player])
    db.session.flush()

    game, hidden = records['game'], records['hidden']

    def add(**fields):
        comment = Comment(comment_type='Comment', **fields)
        db.session.add(comment)
        db.session.flush()
        return comment

    public = add(game_id=game.id, author_name='author', content='Synthetic public body')
    private = add(game_id=game.id, author_name='author', content='Synthetic author-private body',
                  private_to='["recipient"]')
    reply_in_private = add(game_id=game.id, author_name='recipient', parent_id=private.id,
                           content='Synthetic reply under private parent')
    private_reply = add(game_id=game.id, author_name='author', parent_id=public.id,
                        content='Synthetic private reply body', private_to='["recipient"]')
    author_only = add(game_id=game.id, author_name='author', content='Synthetic author-only body',
                      private_to='[]')
    malformed = add(game_id=game.id, author_name='author', content='Synthetic malformed body',
                    private_to='not json')
    leader_private = add(game_id=game.id, author_name='leader_author',
                         content='Synthetic leadership-private body', private_to='["recipient"]')
    hidden_comment = add(game_id=hidden.id, author_name='ordinary', content='Synthetic hidden-game body')
    # Rows as pre-T03 code would have stored them for nonentitled recipients.
    stale = [CommentNotification(recipient_username='ordinary', comment_id=c.id, game_id=c.game_id,
                                 notification_type=kind)
             for c, kind in ((private, 'mention'), (private_reply, 'reply'), (hidden_comment, 'mention'))]
    db.session.add_all(stale)
    db.session.commit()
    return dict(public=public, private=private, reply_in_private=reply_in_private,
                private_reply=private_reply, author_only=author_only, malformed=malformed,
                leader_private=leader_private, hidden_comment=hidden_comment, stale=stale)


# Expected visible comment keys per viewer (baseline: author + explicit recipients).
BASELINE = {
    'ordinary': {'public'},
    'admin': {'public'},
    'author': {'public', 'private', 'reply_in_private', 'private_reply', 'author_only', 'malformed'},
    'recipient': {'public', 'private', 'reply_in_private', 'private_reply', 'leader_private'},
    'leader_author': {'public', 'leader_private'},
    'leadership': {'public'},
}
GAME_KEYS = {'public', 'private', 'reply_in_private', 'private_reply', 'author_only', 'malformed',
             'leader_private'}


def _flatten(comments):
    for comment in comments:
        yield comment
        yield from _flatten(comment.get('replies', []))


def _visible(payload, scenario):
    by_id = {scenario[key].id: key for key in GAME_KEYS}
    seen = list(_flatten(payload))
    return {by_id[c['id']] for c in seen if c['id'] in by_id}, seen


def _assert_no_hidden_bodies(text, scenario, allowed):
    for key in GAME_KEYS - allowed:
        assert scenario[key].content not in text, key


# ── Main film comments API ─────────────────────────────────────────────────

@pytest.mark.parametrize('role', sorted(BASELINE))
def test_film_comments_matrix(client_for, records, scenario, role):
    response = client_for(role).get(f'/film/api/games/{records["game"].id}/comments')
    assert response.status_code == 200
    expected = set(BASELINE[role])
    visible, _ = _visible(response.json['comments'], scenario)
    assert visible == expected
    _assert_no_hidden_bodies(response.text, scenario, expected)


# ── Alternate /api/v1 (no in-repo consumer; fails closed) ──────────────────

@pytest.mark.parametrize('suffix', ['', '/comments'])
def test_alternate_api_hides_private_comments(ordinary, records, suffix):
    response = ordinary.get(f'/api/v1/games/{records["game"].id}{suffix}')
    assert response.status_code == 200
    payload = response.json['game'] if not suffix else response.json
    assert records['private'].id not in {c['id'] for c in payload['comments']}


@pytest.mark.parametrize('suffix', ['', '/comments'])
@pytest.mark.parametrize('role', sorted(BASELINE))
def test_alternate_api_matrix(client_for, records, scenario, role, suffix):
    response = client_for(role).get(f'/api/v1/games/{records["game"].id}{suffix}')
    assert response.status_code == 200
    payload = response.json['game']['comments'] if not suffix else response.json['comments']
    visible, _ = _visible(payload, scenario)
    assert visible == BASELINE[role]
    _assert_no_hidden_bodies(response.text, scenario, BASELINE[role])


def test_alternate_api_write_response_filters_replies(ordinary, records, db):
    from flask_app.models import Comment
    parent = Comment(game_id=records['game'].id, author_name='ordinary', comment_type='Comment',
                     content='Synthetic own parent')
    db.session.add(parent)
    db.session.flush()
    reply = Comment(game_id=records['game'].id, author_name='admin', comment_type='Comment',
                    parent_id=parent.id, content='Synthetic restricted reply', private_to='["recipient"]')
    db.session.add(reply)
    db.session.commit()
    response = ordinary.patch(f'/api/v1/games/{records["game"].id}/comments/{parent.id}',
                              json={'content': 'Synthetic edited parent'})
    assert response.status_code == 200
    assert response.json['comment']['replies'] == []
    assert 'Synthetic restricted reply' not in response.text
    assert db.session.get(Comment, reply.id).content == 'Synthetic restricted reply'


# ── Hidden games: same response as a nonexistent game ─────────────────────

HIDDEN_SURFACES = [
    ('get', '/film/games/{id}', None),
    ('get', '/film/api/games/{id}/comments', None),
    ('post', '/film/api/games/{id}/comments', {'content': 'Synthetic probe'}),
    ('patch', '/film/api/games/{id}/comments/{comment}', {'content': 'Synthetic probe'}),
    ('delete', '/film/api/games/{id}/comments/{comment}', None),
    ('post', '/film/api/games/{id}/track-watch-time', {'seconds_watched': 5}),
    ('get', '/film/api/games/{id}/watch-progress', None),
    ('post', '/film/api/games/{id}/toggle-watched', None),
    ('get', '/api/v1/games/{id}', None),
    ('get', '/api/v1/games/{id}/comments', None),
    ('post', '/api/v1/games/{id}/comments', {'content': 'Synthetic probe'}),
    ('patch', '/api/v1/games/{id}/comments/{comment}', {'content': 'Synthetic probe'}),
    ('delete', '/api/v1/games/{id}/comments/{comment}', None),
    ('post', '/api/v1/games/{id}/track-watch-time', {'seconds_watched': 5}),
]


def _row_counts(db):
    from flask_app.models import Comment, GameWatched, VideoWatchSession
    return tuple(model.query.count() for model in (Comment, GameWatched, VideoWatchSession))


@pytest.mark.parametrize('method,path,body', HIDDEN_SURFACES)
@pytest.mark.parametrize('role', ['ordinary', 'leadership'])
def test_hidden_game_matches_missing_game(client_for, records, scenario, db, role, method, path, body):
    client = client_for(role)
    comment = scenario['hidden_comment']
    before = _row_counts(db)

    def call(game_id):
        url = path.format(id=game_id, comment=comment.id)
        return getattr(client, method)(url, **({'json': body} if body is not None else {}))

    hidden = call(records['hidden'].id)
    missing = call(MISSING_GAME)
    assert hidden.status_code == 404
    assert (hidden.status_code, hidden.get_data()) == (missing.status_code, missing.get_data())
    assert HIDDEN_TITLE not in hidden.text
    assert _row_counts(db) == before
    assert db.session.get(type(comment), comment.id).content == 'Synthetic hidden-game body'


@pytest.mark.parametrize('path', ['/film/games/{id}', '/film/api/games/{id}/comments', '/api/v1/games/{id}'])
def test_hidden_game_denied_directly_but_admin_unchanged(client_for, records, scenario, path):
    url = path.format(id=records['hidden'].id)
    assert client_for('ordinary').get(url).status_code == 404
    assert client_for('admin').get(url).status_code == 200


def test_alternate_api_index_hides_hidden_games(client_for, records):
    for role, listed in (('ordinary', False), ('leadership', False), ('admin', True)):
        response = client_for(role).get('/api/v1/games')
        assert response.status_code == 200
        ids = {g['id'] for g in response.json['games']}
        assert records['game'].id in ids
        assert (records['hidden'].id in ids) is listed, role


def test_my_games_omits_hidden_game_and_comments(client_for, records, scenario, db):
    from flask_app.models import Comment
    db.session.add(Comment(game_id=records['hidden'].id, author_name='admin', comment_type='Comment',
                           content='Synthetic admin hidden note'))
    db.session.commit()
    response = client_for('ordinary').get('/film/my-games')
    assert response.status_code == 200
    assert records['game'].title in response.text
    assert HIDDEN_TITLE not in response.text
    assert 'Synthetic hidden-game body' not in response.text
    response = client_for('admin').get('/film/my-games')
    assert response.status_code == 200
    assert 'Synthetic admin hidden note' in response.text
    assert HIDDEN_TITLE in response.text


def test_tron_data_hidden_ids_act_as_missing(ordinary, records, scenario, db):
    import re
    from flask_app.models import Point
    player = records['users']['ordinary'].player
    hidden_point = Point(game_id=records['hidden'].id, point_index=1, tron_o=True, tron_point=True)
    db.session.add(hidden_point)
    hidden_point.players.append(player)
    records['point'].players.append(player)
    db.session.commit()

    hidden = ordinary.get(f'/film/data?game_ids={records["hidden"].id}')
    missing = ordinary.get(f'/film/data?game_ids={MISSING_GAME}')
    assert hidden.status_code == missing.status_code == 200
    assert hidden.get_data() == missing.get_data()
    assert HIDDEN_TITLE not in hidden.text
    assert player.name not in hidden.text

    # Unfiltered leaderboard counts only the player's visible games.
    full = ordinary.get('/film/data')
    row = re.search(r'cell-title">Synthetic Player</div>.*?hide-mobile">(\d+)<', full.text, re.S)
    assert row.group(1) == '1'


def test_hidden_point_labels_not_offered(ordinary, records, db):
    from flask_app.models import Point
    db.session.add(Point(game_id=records['hidden'].id, point_index=1, pull_play='Synthetic hidden pull'))
    db.session.commit()
    for path in (f'/film/games/{records["game"].id}', f'/api/v1/games/{records["game"].id}'):
        response = ordinary.get(path)
        assert response.status_code == 200
        assert 'Synthetic hidden pull' not in response.text


# ── Notifications ──────────────────────────────────────────────────────────

def _notifications(client):
    response = client.get('/film/api/notifications')
    assert response.status_code == 200
    return response.json


def test_private_reply_notification_does_not_leak(ordinary, admin, records, db):
    from flask_app.models import Comment
    parent = Comment(game_id=records['game'].id, author_name='ordinary',
                     content='Synthetic public parent', comment_type='Comment')
    db.session.add(parent)
    db.session.commit()
    response = admin.post(f'/film/api/games/{records["game"].id}/comments',
                          json={'content': 'Synthetic restricted reply', 'parent_id': parent.id,
                                'private_to': ['recipient']})
    assert response.status_code == 201
    notifications = _notifications(ordinary)['notifications']
    assert all(n['comment_id'] != response.json['comment']['id'] for n in notifications)


def test_reply_under_private_parent_notifies_only_audience(client_for, records, scenario):
    from flask_app.models import CommentNotification
    response = client_for('recipient').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic thread reply @[ordinary] @[leadership]',
              'parent_id': scenario['private'].id})
    assert response.status_code == 201
    new_id = response.json['comment']['id']
    notified = {n.recipient_username for n in CommentNotification.query.filter_by(comment_id=new_id)}
    # Parent author is entitled; mentioned nonrecipients are not.
    assert notified == {'author'}
    assert 'Synthetic thread reply' not in client_for('ordinary').get('/film/api/notifications').text
    assert any(n['comment_id'] == new_id for n in _notifications(client_for('author'))['notifications'])


def test_leadership_nonrecipient_thread_not_notified(client_for, records, scenario, db):
    """Q1 option A: leadership does not confer private-thread access."""
    from flask_app.models import Comment, CommentNotification
    db.session.add(Comment(game_id=records['game'].id, author_name='leadership', comment_type='Comment',
                           parent_id=scenario['leader_private'].id, content='Synthetic leadership reply'))
    db.session.commit()
    response = client_for('recipient').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic recipient reply', 'parent_id': scenario['leader_private'].id})
    assert response.status_code == 201
    notified = {n.recipient_username for n in
                CommentNotification.query.filter_by(comment_id=response.json['comment']['id'])}
    assert notified == {'leader_author'}


def test_hidden_game_mentions_not_notified(admin, ordinary, records, scenario):
    from flask_app.models import CommentNotification
    response = admin.post(f'/film/api/games/{records["hidden"].id}/comments',
                          json={'content': 'Synthetic hidden mention @[ordinary] @[recipient]'})
    assert response.status_code == 201
    assert not CommentNotification.query.filter_by(comment_id=response.json['comment']['id']).count()
    assert HIDDEN_TITLE not in ordinary.get('/film/api/notifications').text


def test_private_mention_notifies_recipients_only(client_for, records, scenario):
    from flask_app.models import CommentNotification
    response = client_for('author').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic note @[ordinary]', 'private_to': ['recipient', 'bystander']})
    assert response.status_code == 201
    notified = {n.recipient_username for n in
                CommentNotification.query.filter_by(comment_id=response.json['comment']['id'])}
    assert notified == {'recipient', 'bystander'}


def test_stale_notifications_omitted_without_delete(ordinary, records, scenario):
    from flask_app.models import CommentNotification
    payload = _notifications(ordinary)
    served = {n['comment_id'] for n in payload['notifications']}
    assert not served & {scenario['private'].id, scenario['private_reply'].id,
                         scenario['hidden_comment'].id}
    assert payload['unread_count'] == 0
    for key in ('private', 'private_reply', 'hidden_comment'):
        assert scenario[key].content not in str(payload)
    assert HIDDEN_TITLE not in str(payload)
    assert CommentNotification.query.filter_by(recipient_username='ordinary').count() == 3


def test_entitled_notification_still_served(client_for, records, scenario):
    response = client_for('author').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic hello @[recipient]', 'private_to': ['recipient']})
    assert response.status_code == 201
    payload = _notifications(client_for('recipient'))
    item = next(n for n in payload['notifications'] if n['comment_id'] == response.json['comment']['id'])
    assert item['content_snippet'] == 'Synthetic hello @[recipient]'
    assert item['notification_type'] == 'private'
    assert payload['unread_count'] == 1


def test_notification_read_is_owner_only(client_for, scenario, db):
    from flask_app.models import CommentNotification
    stale = scenario['stale'][0]
    response = client_for('recipient').post(f'/film/api/notifications/{stale.id}/read')
    assert response.status_code == 404
    response = client_for('recipient').post('/film/api/notifications/read-all')
    assert response.status_code == 200
    db.session.expire_all()
    assert not any(n.is_read for n in CommentNotification.query.filter_by(recipient_username='ordinary'))


# ── Anonymous and admin-only reports ───────────────────────────────────────

ANONYMOUS_PATHS = [
    ('get', '/film/games/{id}'), ('get', '/film/my-games'), ('get', '/film/data'),
    ('get', '/film/api/games/{id}/comments'), ('post', '/film/api/games/{id}/comments'),
    ('post', '/film/api/games/{id}/toggle-watched'), ('get', '/film/api/notifications'),
    ('post', '/film/api/notifications/read-all'), ('get', '/api/v1/games/{id}'),
    ('get', '/api/v1/games/{id}/comments'),
]


@pytest.mark.parametrize('method,path', ANONYMOUS_PATHS)
def test_anonymous_redirected(anonymous, records, scenario, method, path):
    response = getattr(anonymous, method)(path.format(id=records['game'].id))
    assert response.status_code == 302
    assert urlsplit(response.location).path == '/login'


@pytest.mark.parametrize('path', ['/film/api/user/author/comments', '/film/api/user/ordinary/leadership-tags'])
@pytest.mark.parametrize('role', ['ordinary', 'leadership', 'author', 'recipient'])
def test_admin_reports_deny_nonadmins(client_for, scenario, role, path):
    response = client_for(role).get(path)
    assert response.status_code == 302
    assert urlsplit(response.location).path == '/'


# ── Repair round 1: Q1 option A, reports, legacy rows, edit history ──────────

@pytest.mark.parametrize('leadership_author', [False, True])
@pytest.mark.parametrize('relation', ['author', 'recipient', 'nonrecipient'])
def test_admin_reports_and_counts_share_viewer_policy(
        admin, records, db, app, relation, leadership_author):
    from flask import template_rendered
    from flask_app.models import Comment, CommentNotification

    author = records['users']['admin' if relation == 'author' else 'ordinary']
    author.is_leadership = leadership_author
    audience = '["admin", "recipient"]' if relation == 'recipient' else '["recipient"]'
    parent = Comment(game_id=records['game'].id, author_name=author.username,
                     content='Synthetic report private parent', comment_type='Comment',
                     private_to=audience)
    db.session.add(parent)
    db.session.flush()
    reply = Comment(game_id=records['game'].id, author_name=author.username,
                    content='Synthetic report public reply', comment_type='Comment', parent_id=parent.id)
    db.session.add(reply)
    db.session.flush()
    grandchild = Comment(game_id=records['game'].id, author_name=author.username,
                         content='Synthetic report deep reply', comment_type='Comment', parent_id=reply.id)
    public = Comment(game_id=records['game'].id, author_name=author.username,
                     content='Synthetic report public control', comment_type='Comment')
    db.session.add_all([grandchild, public])
    db.session.flush()
    comments = [parent, reply, grandchild, public]
    for i, comment in enumerate(comments):
        db.session.add(CommentNotification(recipient_username='recipient', comment_id=comment.id,
                                          game_id=comment.game_id, notification_type='private',
                                          is_read=i % 2 == 0))
    db.session.commit()

    expected = {c.id for c in (comments if relation != 'nonrecipient' else [public])}
    listing = admin.get(f'/film/api/user/{author.username}/comments')
    tags = admin.get('/film/api/user/recipient/leadership-tags')
    assert listing.status_code == tags.status_code == 200
    ids = {c.id for c in comments}
    assert {c['id'] for c in listing.json['comments']} & ids == expected
    assert {t['comment_id'] for t in tags.json['tags']} == (expected if leadership_author else set())
    if relation == 'nonrecipient':
        for comment in (parent, reply, grandchild):
            assert comment.content not in listing.text + tags.text

    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    with template_rendered.connected_to(capture, app):
        dashboard = admin.get('/film/analytics')
    assert dashboard.status_code == 200
    context = contexts[-1]
    total = 0
    for row in context['user_analytics']:
        name = row['user'].username
        visible_comments = admin.get(f'/film/api/user/{name}/comments').json['comments']
        visible_tags = admin.get(f'/film/api/user/{name}/leadership-tags').json['tags']
        assert row['comment_count'] == len(visible_comments)
        assert row['leadership_notif_total'] == len(visible_tags)
        assert row['leadership_notif_read'] == sum(t['is_read'] for t in visible_tags)
        total += len(visible_comments)
    assert context['total_comments'] == total


@pytest.mark.parametrize('surface', ['film', 'alternate', 'admin-report'])
@pytest.mark.parametrize('stored', [
    pytest.param('', id='empty-string-was-public'),
    pytest.param('"recipient"', id='json-string-was-substring-membership'),
    pytest.param('{"recipient": true}', id='json-object-was-key-membership'),
])
def test_legacy_nonlist_audiences_fail_closed(client_for, records, db, stored, surface):
    """Before T03, film GET exposed '' to everyone and strings/objects to matching
    usernames. Now all three stored forms are author-only, not public/recipients.
    These are stored legacy rows, not changes to T04 request validation.
    """
    from flask_app.models import Comment
    comment = Comment(game_id=records['game'].id, author_name='ordinary',
                      content='Synthetic legacy private body', comment_type='Comment', private_to=stored)
    db.session.add(comment)
    db.session.commit()
    if surface == 'admin-report':
        # Both viewers must be admins to exercise report content, not its role gate.
        records['users']['ordinary'].is_admin = True
        records['users']['recipient'].is_admin = True
        db.session.commit()
        path = '/film/api/user/ordinary/comments'
    else:
        prefix = '/film/api' if surface == 'film' else '/api/v1'
        path = f'{prefix}/games/{records["game"].id}/comments'
    for role in ('ordinary', 'recipient'):
        response = client_for(role).get(path)
        assert response.status_code == 200
        assert (comment.content in response.text) is (role == 'ordinary')
        assert (comment.id in {c['id'] for c in response.json['comments']}) is (role == 'ordinary')


def test_hidden_game_ancestor_denies_cross_game_reply(client_for, records, db):
    from flask_app.models import Comment, CommentNotification
    parent = Comment(game_id=records['hidden'].id, author_name='ordinary',
                     content='Synthetic hidden ancestor', comment_type='Comment')
    db.session.add(parent)
    db.session.flush()
    child = Comment(game_id=records['game'].id, author_name='ordinary', parent_id=parent.id,
                    content='Synthetic cross-game descendant', comment_type='Comment')
    db.session.add(child)
    db.session.flush()
    for role in ('ordinary', 'admin'):
        db.session.add(CommentNotification(recipient_username=role, comment_id=child.id,
                                          game_id=child.game_id, notification_type='mention'))
    db.session.commit()
    assert child.content in client_for('admin').get('/film/api/notifications').text
    assert child.content not in client_for('ordinary').get('/film/api/notifications').text
    response = client_for('admin').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic cross-game deep reply @[ordinary]', 'parent_id': child.id})
    assert response.status_code == 201
    assert CommentNotification.query.filter_by(comment_id=response.json['comment']['id']).count() == 0


def test_deep_reply_notification_creation_and_revoked_ancestor(client_for, records, scenario, db):
    from flask_app.models import CommentNotification
    response = client_for('author').post(
        f'/film/api/games/{records["game"].id}/comments',
        json={'content': 'Synthetic grandchild @[recipient] @[ordinary] @[leadership]',
              'parent_id': scenario['reply_in_private'].id})
    assert response.status_code == 201
    comment_id = response.json['comment']['id']
    rows = CommentNotification.query.filter_by(comment_id=comment_id).all()
    assert [n.recipient_username for n in rows] == ['recipient']
    assert any(n['comment_id'] == comment_id for n in _notifications(client_for('recipient'))['notifications'])
    assert all(n['comment_id'] != comment_id for n in _notifications(client_for('ordinary'))['notifications'])
    # Grandparent changes do not rewrite descendant rows; reads enforce the full chain.
    scenario['private'].private_to = '[]'
    db.session.commit()
    assert all(n['comment_id'] != comment_id for n in _notifications(client_for('recipient'))['notifications'])
    assert CommentNotification.query.filter_by(comment_id=comment_id).count() == 1


def test_comment_edit_preserves_entitled_notification_history(client_for, records, scenario, db):
    from datetime import datetime
    from flask_app.models import CommentNotification
    path = f'/film/api/games/{records["game"].id}/comments'
    response = client_for('author').post(path, json={
        'content': 'Synthetic initial note', 'private_to': ['recipient', 'bystander']})
    assert response.status_code == 201
    comment_id = response.json['comment']['id']
    kept = CommentNotification.query.filter_by(comment_id=comment_id, recipient_username='recipient').one()
    kept.is_read = True
    kept.read_at = datetime(2026, 1, 2, 3, 4, 5)
    db.session.commit()
    history = (kept.id, kept.created_at, kept.read_at)
    for _ in range(2):
        response = client_for('author').patch(f'{path}/{comment_id}', json={
            'content': 'Synthetic updated note', 'private_to': ['recipient', 'ordinary']})
        assert response.status_code == 200
        db.session.expire_all()
        rows = CommentNotification.query.filter_by(comment_id=comment_id).all()
        assert {n.recipient_username for n in rows} == {'recipient', 'ordinary'}
        kept = next(n for n in rows if n.recipient_username == 'recipient')
        assert (kept.id, kept.created_at, kept.read_at) == history
        assert kept.is_read
        added = next(n for n in rows if n.recipient_username == 'ordinary')
        assert not added.is_read and added.read_at is None
    # Removing a mention/audience target on a now-public comment preserves history
    # for recipients who still have access, without generating duplicate notices.
    response = client_for('author').patch(f'{path}/{comment_id}', json={
        'content': 'Synthetic public edit without mentions', 'private_to': None})
    assert response.status_code == 200
    assert CommentNotification.query.filter_by(comment_id=comment_id).count() == 2
    db.session.expire_all()
    kept = db.session.get(CommentNotification, history[0])
    assert kept.is_read and kept.read_at == history[2]


@pytest.mark.parametrize('game_key', ['game', 'hidden'])
@pytest.mark.parametrize('prefix', ['/film/api', '/api/v1'])
def test_admin_comment_writes_and_watch_tracking_unchanged(admin, records, db, game_key, prefix):
    from flask_app.models import Comment, VideoWatchSession
    game_id = records[game_key].id
    path = f'{prefix}/games/{game_id}'
    created = admin.post(path + '/comments', json={'content': 'Synthetic admin write'})
    assert created.status_code == 201
    comment_id = created.json['comment']['id']
    edited = admin.patch(f'{path}/comments/{comment_id}', json={'content': 'Synthetic admin edit'})
    assert edited.status_code == 200
    assert db.session.get(Comment, comment_id).content == 'Synthetic admin edit'
    watched = admin.post(path + '/track-watch-time', json={'seconds_watched': 5})
    assert watched.status_code == 200
    row = VideoWatchSession.query.filter_by(user_id=records['users']['admin'].id, game_id=game_id).one()
    assert row.watch_duration_seconds == 5
    assert admin.delete(f'{path}/comments/{comment_id}').status_code == 200
    assert db.session.get(Comment, comment_id) is None


@pytest.mark.parametrize('game_key', ['game', 'hidden'])
def test_admin_watch_progress_and_toggle_unchanged(admin, records, db, game_key):
    from flask_app.models import GameWatched
    game_id = records[game_key].id
    path = f'/film/api/games/{game_id}'
    assert admin.post(path + '/track-watch-time', json={
        'seconds_watched': 5, 'playback_position': 65}).status_code == 200
    response = admin.get(path + '/watch-progress')
    assert response.status_code == 200
    assert response.json == {'last_position': 65}
    for expected in (True, False):
        response = admin.post(path + '/toggle-watched')
        assert response.status_code == 200
        assert response.json == {'watched': expected, 'game_id': game_id}
        assert GameWatched.query.filter_by(user_id=records['users']['admin'].id, game_id=game_id).count() == int(expected)
