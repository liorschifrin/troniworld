"""T05 slice 1: every state-changing request needs the session CSRF token (synthetic only)."""
from io import BytesIO
import json
from pathlib import Path
import re

import pytest
from conftest import synthetic_image
from sqlalchemy import select

ERROR = {'error': 'CSRF token missing or invalid'}
FLASH = 'Your session expired or the form was invalid'
TEMPLATES = Path(__file__).resolve().parents[1] / 'flask_app/templates'
CSV = b',O\n,1\n,\n\nSynthetic roster player,1\n'


@pytest.fixture
def writes(records, db):
    """Synthetic rows for every write route, plus the inventory of write requests."""
    from flask_app.models import (ArticleComment, ArticleCommentNotification, Comment,
                                  CommentNotification, Player, Point, Post, User)
    game, point = records['game'], records['point']
    player = Player(name='Synthetic roster player')
    unlinked = Player(name='Synthetic unlinked player')
    game.roster.append(player)
    post = Post(title='Synthetic post', author='Synthetic author', content='Synthetic body')
    disposable = User(username='Disposable', hashed_password='synthetic-unused-hash')
    hidden_point = Point(game_id=game.id, point_index=2, tron_o=True, tron_point=True, hidden_by_import=True)
    db.session.add_all([player, unlinked, post, disposable, hidden_point])
    db.session.flush()
    article = ArticleComment(post_id=post.id, author_name='ordinary', content='Synthetic article comment')
    comment = Comment(game_id=game.id, author_name='ordinary', content='Synthetic comment',
                      comment_type='Comment')
    db.session.add_all([article, comment])
    db.session.flush()
    db.session.add_all([
        ArticleCommentNotification(recipient_username='ordinary', comment_id=article.id,
                                   post_id=post.id, notification_type='reply'),
        CommentNotification(recipient_username='ordinary', comment_id=comment.id,
                            game_id=game.id, notification_type='mention'),
    ])
    db.session.commit()
    article_notif = ArticleCommentNotification.query.one().id
    film_notif = CommentNotification.query.one().id
    film = f'/film/api/games/{game.id}'

    def apply_body():
        from flask_app import csv_import
        sheet, _ = csv_import.parse_game_csv(CSV)
        token = csv_import.state_token(csv_import.load_state(game), {'Synthetic roster player'})
        return {'csv_text': CSV.decode(), 'state_token': token, 'confirm_hidden': '1'}

    image = lambda: {'upload': (BytesIO(synthetic_image()), 'synthetic.png')}
    # (role, method, path, client kind, body factory, legitimate status)
    return {
        'login': ('anonymous', 'post', '/login', 'form',
                  lambda: {'username': 'ordinary', 'password': 'synthetic-member-password'}, 302),
        'logout': ('ordinary', 'post', '/logout', 'form', dict, 302),
        'register': ('admin', 'post', '/register', 'form', lambda: {'username': 'Synthetic new'}, 302),
        'new-post': ('admin', 'post', '/new_post', 'form',
                     lambda: {'title': 'Synthetic', 'author': 'Synthetic', 'content': 'Synthetic'}, 302),
        'edit-post': ('admin', 'post', f'/post/{post.id}/edit', 'form',
                      lambda: {'title': 'Synthetic edit', 'author': 'Synthetic', 'content': 'Synthetic',
                               'created_at': '2026-10-25'}, 302),
        'delete-post': ('admin', 'post', f'/post/{post.id}/delete', 'form', dict, 302),
        'article-create': ('ordinary', 'post', f'/post/{post.id}/comments', 'fetch',
                           lambda: {'content': 'Synthetic'}, 201),
        'article-edit': ('ordinary', 'patch', f'/post/{post.id}/comments/{article.id}', 'fetch',
                         lambda: {'content': 'Synthetic edit'}, 200),
        'article-delete': ('ordinary', 'delete', f'/post/{post.id}/comments/{article.id}', 'fetch', None, 200),
        'upload-image': ('admin', 'post', '/upload_image', 'multipart', image, 201),
        'article-notif-read': ('ordinary', 'post', f'/api/article-notifications/{article_notif}/read',
                               'jquery', None, 200),
        'article-notif-read-all': ('ordinary', 'post', '/api/article-notifications/read-all',
                                   'jquery', None, 200),
        'user-create': ('admin', 'post', '/admin/users', 'form',
                        lambda: {'action': 'create', 'username': 'Synthetic created'}, 302),
        'user-archive': ('admin', 'post', '/admin/users', 'form',
                         lambda: {'action': 'archive', 'user_id': str(disposable.id)}, 302),
        'user-toggle-role': ('admin', 'post', '/admin/users', 'ajax-form',
                             lambda: {'action': 'toggle_role', 'user_id': str(disposable.id),
                                      'role_type': 'leadership'}, 200),
        'create-all-players': ('admin', 'post', '/admin/users/create_all_players', 'form', dict, 302),
        'new-tournament': ('admin', 'post', '/film/tournaments/new', 'form',
                           lambda: {'name': 'Synthetic tournament'}, 302),
        'new-game': ('admin', 'post', '/film/games/new', 'form',
                     lambda: {'title': 'Synthetic', 'opponent': 'Synthetic'}, 302),
        'edit-game': ('admin', 'post', f'/film/games/{game.id}/edit', 'form',
                      lambda: {'title': 'Synthetic edit', 'opponent': 'Synthetic'}, 302),
        'upload-csv': ('admin', 'post', f'/film/games/{game.id}/upload_csv', 'form',
                       lambda: {'csv_file': (BytesIO(CSV), 'synthetic.csv')}, 200),
        'upload-csv-apply': ('admin', 'post', f'/film/games/{game.id}/upload_csv/apply', 'form',
                             apply_body, 302),
        'restore-hidden-point': ('admin', 'post',
                                 f'/film/games/{game.id}/points/{hidden_point.id}/restore_hidden', 'form',
                                 dict, 302),
        'delete-player-sheet': ('admin', 'post', f'/film/games/{game.id}/delete_player_sheet', 'form',
                                dict, 302),
        'comment-create': ('ordinary', 'post', film + '/comments', 'fetch',
                           lambda: {'content': 'Synthetic'}, 201),
        'comment-edit': ('ordinary', 'patch', film + f'/comments/{comment.id}', 'fetch',
                         lambda: {'content': 'Synthetic edit'}, 200),
        'comment-delete': ('ordinary', 'delete', film + f'/comments/{comment.id}', 'fetch', None, 200),
        'point-patch': ('admin', 'patch', film + f'/points/{point.id}', 'fetch',
                        lambda: {'pull_play': 'Synthetic'}, 200),
        'player-sheet': ('admin', 'post', film + '/update_player_sheet', 'fetch',
                         lambda: {'changes': [{'point_id': point.id, 'player_name': player.name,
                                               'in_point': True}]}, 200),
        'watch-time': ('ordinary', 'post', film + '/track-watch-time', 'fetch',
                       lambda: {'seconds_watched': 5, 'playback_position': 20,
                                'client_session_id': 'tab-1', 'event_id': 'tab-1:1'}, 200),
        'watch-time-beacon': ('ordinary', 'post', film + '/track-watch-time', 'beacon',
                              lambda: {'seconds_watched': 5, 'playback_position': 20,
                                     'client_session_id': 'tab-1', 'event_id': 'tab-1:1'}, 200),
        'notif-read': ('ordinary', 'post', f'/film/api/notifications/{film_notif}/read', 'fetch', None, 200),
        'notif-read-all': ('ordinary', 'post', '/film/api/notifications/read-all', 'fetch', None, 200),
        'toggle-watched': ('ordinary', 'post', film + '/toggle-watched', 'fetch', None, 200),
    }


@pytest.fixture
def session_client(app, records):
    """A browser session whose token was minted by the server, with no default header."""
    def make(role):
        client = app.test_client()
        if role != 'anonymous':
            with client.session_transaction() as session:
                session['user_id'] = records['users'][role].id
        assert client.get('/login').status_code == 200
        with client.session_transaction() as session:
            return client, session['csrf_token']
    return make


def snapshot(db, app):
    """All persisted values (not only counts) plus uploaded files."""
    db.session.expire_all()
    tables = {table.name: [tuple(row) for row in db.session.execute(
        select(table).order_by(*table.primary_key.columns))]
        for table in db.metadata.sorted_tables}
    return tables, sorted(p.name for p in Path(app.config['UPLOAD_FOLDER']).iterdir())


def send(client, write, token, *, place=None):
    """Send one write the way its real client does; place overrides where the token goes."""
    _, method, path, kind, body, _ = write
    payload = body() if body else None
    place = place or {'form': 'field', 'multipart': 'header', 'beacon': 'body'}.get(kind, 'header')
    headers = {}
    if token is not None and place == 'header':
        headers['X-CSRFToken'] = token
    if kind == 'ajax-form':
        headers['X-Requested-With'] = 'XMLHttpRequest'
    if kind in ('form', 'multipart', 'ajax-form'):
        payload = dict(payload)
        if token is not None and place == 'field':
            payload['csrf_token'] = token
        return getattr(client, method)(path, data=payload, headers=headers)
    if kind == 'beacon' or place == 'body':
        # A Blob-typed beacon; string beacons are the separate T09 content-type defect.
        payload = dict(payload or {})
        if token is not None:
            payload['csrf_token'] = token
        return client.post(path, data=json.dumps(payload), content_type='application/json',
                           headers=headers)
    if payload is None:
        return getattr(client, method)(path, headers=headers)
    return getattr(client, method)(path, json=payload, headers=headers)


def logged_in(client):
    with client.session_transaction() as session:
        return 'user_id' in session


def assert_denied(response, kind):
    assert response.status_code == 403
    if kind == 'form':
        assert response.mimetype == 'text/html'
        assert FLASH in response.get_data(as_text=True)
    else:
        assert response.get_json() == ERROR


WRITE_IDS = ['login', 'logout', 'register', 'new-post', 'edit-post', 'delete-post', 'article-create',
             'article-edit', 'article-delete', 'upload-image', 'article-notif-read',
             'article-notif-read-all', 'user-create', 'user-archive', 'user-toggle-role',
             'create-all-players', 'new-tournament', 'new-game', 'edit-game', 'upload-csv',
             'upload-csv-apply', 'restore-hidden-point',
             'delete-player-sheet', 'comment-create', 'comment-edit', 'comment-delete', 'point-patch',
             'player-sheet', 'watch-time', 'watch-time-beacon', 'notif-read', 'notif-read-all',
             'toggle-watched']


def test_write_inventory_covers_every_state_changing_route(app, writes):
    routed = {(method.lower(), rule.endpoint) for rule in app.url_map.iter_rules()
              for method in rule.methods - {'GET', 'HEAD', 'OPTIONS'}}
    adapter = app.url_map.bind('localhost')
    covered = {(method, adapter.match(path.split('?')[0], method=method.upper())[0])
               for _, method, path, *_ in writes.values()}
    assert sorted(writes) == sorted(WRITE_IDS)
    assert routed == covered


@pytest.mark.parametrize('name', WRITE_IDS)
def test_legitimate_write_with_token_succeeds(session_client, writes, db, app, name):
    write = writes[name]
    client, token = session_client(write[0])
    before = snapshot(db, app)
    response = send(client, write, token)
    assert response.status_code == write[5], response.get_data(as_text=True)[:500]
    if name == 'logout':
        assert not logged_in(client)
    elif name == 'upload-csv':
        assert snapshot(db, app) == before  # a preview never writes
    else:
        assert snapshot(db, app) != before
    if name == 'login':
        assert logged_in(client)


@pytest.mark.parametrize('variant', ['missing', 'wrong', 'cross-session', 'no-session-token'])
@pytest.mark.parametrize('name', WRITE_IDS)
def test_forged_write_is_denied_without_writes(session_client, app, records, writes, db, name, variant):
    write = writes[name]
    client, own = session_client(write[0])
    token = {'missing': None, 'wrong': own[::-1]}.get(variant)
    if variant == 'cross-session':
        # A real token from the attacker's own session is not valid in the victim's.
        _, token = session_client(write[0])
        assert token != own
    if variant == 'no-session-token':
        with client.session_transaction() as session:
            session.pop('csrf_token')
        _, token = session_client('anonymous')
    before = snapshot(db, app)
    was_logged_in = logged_in(client)
    response = send(client, write, token)
    assert_denied(response, 'form' if write[3] == 'form' else 'json')
    assert snapshot(db, app) == before
    assert logged_in(client) == was_logged_in


def test_json_body_token_is_only_read_for_the_beacon(session_client, writes, db, app):
    # Body tokens exist only because sendBeacon cannot set headers.
    client, token = session_client('ordinary')
    before = snapshot(db, app)
    response = send(client, writes['comment-create'], token, place='body')
    assert_denied(response, 'json')
    assert snapshot(db, app) == before


def test_form_token_field_is_accepted_for_json_fetch_routes(session_client, writes, db, app):
    # Multipart fetches (CKEditor upload) may carry the field instead of the header.
    client, token = session_client('admin')
    response = send(client, writes['upload-image'], token, place='field')
    assert response.status_code == 201


def test_string_beacon_with_token_passes_csrf(session_client, writes):
    # A text/plain body from an older page still reaches the handler; CSRF accepts it.
    client, token = session_client('ordinary')
    response = client.post(writes['watch-time'][2], content_type='text/plain;charset=UTF-8',
                           data=json.dumps({'seconds_watched': 5, 'client_session_id': 't', 'event_id': 't:1',
                                       'csrf_token': token}))
    assert response.status_code != 403
    response = client.post(writes['watch-time'][2], content_type='text/plain;charset=UTF-8',
                           data=json.dumps({'seconds_watched': 5}))
    assert_denied(response, 'json')


@pytest.mark.parametrize('token', ['', 'é' * 8, 'x' * 10000], ids=['empty', 'non-ascii', 'oversized'])
def test_malformed_tokens_are_denied(session_client, writes, db, app, token):
    client, _ = session_client('ordinary')
    before = snapshot(db, app)
    response = client.post(writes['comment-create'][2], json={'content': 'Synthetic'},
                           headers={'X-CSRFToken': token})
    assert_denied(response, 'json')
    assert snapshot(db, app) == before


def test_query_and_cookie_tokens_are_denied(session_client, writes, db, app):
    client, token = session_client('ordinary')
    path = writes['comment-create'][2]
    before = snapshot(db, app)
    assert_denied(client.post(f'{path}?csrf_token={token}', json={'content': 'Synthetic'}), 'json')
    client.set_cookie('csrf_token', token)
    assert_denied(client.post(path, json={'content': 'Synthetic'}), 'json')
    assert snapshot(db, app) == before


def page_token(client):
    assert client.get('/login').status_code == 200
    with client.session_transaction() as session:
        return session['csrf_token']


def test_token_rotates_at_login_and_register(session_client, records, writes, db, app):
    game = records['game'].id
    comment = {'json': {'content': 'Synthetic'}}
    client, old = session_client('anonymous')
    response = client.post('/login', data={'username': 'ordinary', 'password': 'synthetic-member-password',
                                           'csrf_token': old})
    assert response.status_code == 302 and logged_in(client)
    new = page_token(client)
    assert new != old
    before = snapshot(db, app)
    assert_denied(client.post(f'/film/api/games/{game}/comments', headers={'X-CSRFToken': old}, **comment),
                  'json')
    assert snapshot(db, app) == before
    assert client.post(f'/film/api/games/{game}/comments', headers={'X-CSRFToken': new},
                       **comment).status_code == 201
    # Logout keeps the token; the next sign-in rotates it.
    assert client.post('/logout', data={'csrf_token': new}).status_code == 302
    assert not logged_in(client)
    assert page_token(client) == new

    client, old = session_client('admin')
    assert client.post('/register', data={'username': 'Synthetic new', 'csrf_token': old}).status_code == 302
    new = page_token(client)
    assert new != old
    before = snapshot(db, app)
    assert_denied(client.post(f'/film/api/games/{game}/comments', headers={'X-CSRFToken': old}, **comment),
                  'json')
    assert snapshot(db, app) == before


@pytest.mark.parametrize('role,path', [
    ('anonymous', '/'), ('anonymous', '/login'), ('anonymous', '/login?next=/film/games'),
    ('anonymous', '/post/{post}'), ('anonymous', '/post/{post}/comments'),
    ('ordinary', '/film/games'), ('ordinary', '/film/games/{game}'), ('ordinary', '/film/my-games'),
    ('ordinary', '/film/api/games/{game}/comments'), ('ordinary', '/film/api/notifications'),
    ('ordinary', '/api/article-notifications'), ('ordinary', '/film/api/games/{game}/watch-progress'),
    ('admin', '/film/analytics'), ('admin', '/admin/users'),
])
def test_get_stays_public_without_token(app, records, writes, role, path):
    from flask_app.models import Post
    client = app.test_client()
    if role != 'anonymous':
        with client.session_transaction() as session:
            session['user_id'] = records['users'][role].id
    response = client.get(path.format(post=Post.query.one().id, game=records['game'].id))
    assert response.status_code == 200


def test_get_logout_is_unchanged(client_for):
    # Navigation links still log out by GET; see the documented limitation.
    client = client_for('ordinary')
    client.environ_base.pop('HTTP_X_CSRFTOKEN')
    assert client.get('/logout').status_code == 302
    assert not logged_in(client)


def test_unrouted_writes_keep_404_and_405(app):
    client = app.test_client()
    assert client.post('/no-such-route').status_code == 404
    assert client.post('/film/games').status_code == 405


@pytest.mark.parametrize('role,path', [
    ('anonymous', '/login'), ('anonymous', '/login?next=/film/games'), ('admin', '/register'),
    ('admin', '/new_post'), ('admin', '/post/{post}/edit'), ('admin', '/admin/users'),
    ('admin', '/film/tournaments/new'), ('admin', '/film/games/new'), ('admin', '/film/games/{game}/edit'),
    ('admin', '/film/games/{game}/upload_csv'), ('admin', '/film/games/{game}'),
    ('ordinary', '/post/{post}'), ('ordinary', '/film/games'),
])
def test_rendered_pages_carry_the_session_token(session_client, records, writes, db, role, path):
    from flask_app.models import Point, Post
    # A rostered point gives the game page its player sheet and hidden delete form.
    point = db.session.get(Point, records['point'].id)
    point.players.append(records['game'].roster[0])
    db.session.commit()
    client, token = session_client(role)
    html = client.get(path.format(post=Post.query.one().id, game=records['game'].id)).get_data(as_text=True)
    assert f'const CSRF_TOKEN = "{token}";' in html
    forms = re.findall(r'<form\b[^>]*method="post"[^>]*>(.*?)</form>', html, re.I | re.S)
    for form in forms:
        assert f'<input type="hidden" name="csrf_token" value="{token}">' in form
    if path not in ('/post/{post}', '/film/games'):
        assert forms


def template_sources():
    return {path.relative_to(TEMPLATES).as_posix(): path.read_text()
            for path in TEMPLATES.rglob('*.html') if 'unused' not in path.parts}


def call_arguments(source, name):
    """Yield the full argument text of every call to name(...)."""
    for match in re.finditer(re.escape(name) + r'\(', source):
        depth, start = 0, match.end() - 1
        for index in range(start, len(source)):
            depth += {'(': 1, ')': -1}.get(source[index], 0)
            if depth == 0:
                yield source[start + 1:index]
                break


def test_every_template_write_client_carries_the_token():
    fetch_writes = forms = beacons = jquery = 0
    for name, source in template_sources().items():
        for args in call_arguments(source, 'fetch'):
            if re.search(r"method:\s*'(POST|PUT|PATCH|DELETE)'", args, re.I):
                fetch_writes += 1
                assert "'X-CSRFToken': CSRF_TOKEN" in args, (name, args[:120])
        for form in re.findall(r'<form\b[^>]*>\s*\S[^\n]*', source):
            if re.search(r'method="post"', form, re.I):
                forms += 1
                assert 'name="csrf_token" value="{{ csrf_token() }}"' in form, (name, form)
        for args in call_arguments(source, 'navigator.sendBeacon'):
            beacons += 1
            blob = re.search(r"new Blob\(\[(\w+)\],\s*\{\s*type:\s*'application/json'\s*\}\)", args)
            assert blob, (name, 'the beacon body must be a JSON-typed Blob')
            variable = blob.group(1)
            assigned = re.search(rf'const {variable} = JSON\.stringify\(\{{(.*?)\}}\);', source, re.S)
            assert assigned and 'csrf_token: CSRF_TOKEN' in assigned.group(1), name
        if 'jQuery.post(' in source or '$.post(' in source or '$.ajax(' in source:
            jquery += source.count('jQuery.post(')
            assert name == 'articles/base.html'
    base = template_sources()['articles/base.html']
    prefilter = base.index('jQuery.ajaxPrefilter')
    assert "xhr.setRequestHeader('X-CSRFToken', CSRF_TOKEN)" in base[prefilter:prefilter + 300]
    assert prefilter < base.index('jQuery.post(')
    # Exact inventory; a new client must be added here deliberately.
    assert (fetch_writes, forms, beacons, jquery) == (20, 16, 1, 3)
