"""T04 request contracts, atomic rejection, and normal-client controls (synthetic only)."""
import json

import pytest
from sqlalchemy import select


@pytest.fixture
def inputs(records, db):
    from flask_app.models import ArticleComment, Comment, Game, Player, Point, Post
    game = records['game']
    other = Game(title='Synthetic other game', opponent='Synthetic visitors')
    player = Player(name='Synthetic roster player')
    outsider = Player(name='Synthetic outside player')
    game.roster.append(player)
    post = Post(title='Synthetic post', author='Synthetic author', content='Synthetic body')
    other_post = Post(title='Synthetic other post', author='Synthetic author', content='Synthetic body')
    db.session.add_all([other, player, outsider, post, other_post])
    db.session.flush()
    foreign_point = Point(game_id=other.id, point_index=1)
    parent = Comment(game_id=game.id, author_name='ordinary', content='Synthetic parent', comment_type='Comment')
    foreign = Comment(game_id=other.id, author_name='ordinary', content='Synthetic foreign parent', comment_type='Comment')
    article = ArticleComment(post_id=post.id, author_name='ordinary', content='Synthetic article parent')
    foreign_article = ArticleComment(post_id=other_post.id, author_name='ordinary', content='Synthetic foreign article')
    db.session.add_all([foreign_point, parent, foreign, article, foreign_article])
    db.session.flush()
    reply = Comment(game_id=game.id, author_name='ordinary', parent_id=parent.id,
                    content='Synthetic reply', comment_type='Comment')
    article_reply = ArticleComment(post_id=post.id, author_name='ordinary', parent_id=article.id,
                                   content='Synthetic article reply')
    db.session.add_all([reply, article_reply])
    db.session.commit()
    base = f'/film/api/games/{game.id}'
    return dict(player=player, outsider=outsider, parent=parent, foreign=foreign, reply=reply,
                foreign_point=foreign_point, article=article, foreign_article=foreign_article,
                article_reply=article_reply, post=post,
                routes={
                    'film-create': ('post', base + '/comments', 'ordinary'),
                    'film-edit': ('patch', base + f'/comments/{parent.id}', 'ordinary'),
                    'point': ('patch', base + f'/points/{records["point"].id}', 'admin'),
                    'sheet': ('post', base + '/update_player_sheet', 'admin'),
                    'article-create': ('post', f'/post/{post.id}/comments', 'ordinary'),
                    'article-edit': ('patch', f'/post/{post.id}/comments/{article.id}', 'ordinary'),
                })


def snapshot(db):
    """Row counts AND all persisted values, including associations and notifications."""
    db.session.expire_all()
    return {table.name: [tuple(row) for row in db.session.execute(
        select(table).order_by(*table.primary_key.columns))]
        for table in db.metadata.sorted_tables}


def call(client_for, inputs, route, payload=None, **kwargs):
    method, path, role = inputs['routes'][route]
    if not kwargs:
        kwargs = {'data': json.dumps(payload), 'content_type': 'application/json'}
    return getattr(client_for(role), method)(path, **kwargs)


def rejected(db, operation, status=400):
    before = snapshot(db)
    response = operation()
    assert response.status_code == status
    assert response.is_json and set(response.json) == {'error'}
    assert isinstance(response.json['error'], str) and response.json['error']
    assert snapshot(db) == before
    return response


BODY_ROUTES = ['film-create', 'film-edit', 'article-create', 'article-edit', 'point', 'sheet']


@pytest.mark.parametrize('route', BODY_ROUTES)
@pytest.mark.parametrize('body', [None, [], 'text', 42, True])
def test_nonobject_body_rejected(client_for, inputs, db, route, body):
    rejected(db, lambda: call(client_for, inputs, route, body))


@pytest.mark.parametrize('route', BODY_ROUTES)
@pytest.mark.parametrize('body,content_type', [('{', 'application/json'), ('', 'application/json'),
                                             ('{}', 'text/plain')])
def test_malformed_json_rejected(client_for, inputs, db, route, body, content_type):
    rejected(db, lambda: call(client_for, inputs, route, data=body, content_type=content_type))


@pytest.mark.parametrize('route', ['film-create', 'film-edit', 'article-create', 'article-edit'])
@pytest.mark.parametrize('value', [None, 0, False, [], {}, '', ' \n '])
def test_content_rejected(client_for, inputs, db, route, value):
    rejected(db, lambda: call(client_for, inputs, route, {'content': value}))


@pytest.mark.parametrize('route', ['film-create', 'film-edit', 'article-create', 'article-edit', 'sheet'])
def test_required_fields(client_for, inputs, db, route):
    rejected(db, lambda: call(client_for, inputs, route, {}))


@pytest.mark.parametrize('route', BODY_ROUTES)
def test_unsupported_fields(client_for, inputs, db, route):
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', 'is_hidden': 'false'}))


INVALID_TIMES = ['12', '0);alert(1)//', -1, 86400.01, True, False, float('nan'),
                 float('inf'), -float('inf'), [], {}, 10 ** 100]


@pytest.mark.parametrize('route,field', [('film-create', 'timestamp'), ('point', 'timestamp_start')])
@pytest.mark.parametrize('value', INVALID_TIMES)
def test_invalid_timestamp(client_for, inputs, db, route, field, value):
    payload = {field: value}
    if route == 'film-create':
        payload['content'] = 'Synthetic timed comment'
    else:
        payload['pull_play'] = 'Must not persist'
    rejected(db, lambda: call(client_for, inputs, route, payload))


@pytest.mark.parametrize('route,field', [('film-create', 'timestamp'), ('point', 'timestamp_start')])
@pytest.mark.parametrize('value', [None, 0, 1.25, 86400])
def test_valid_timestamp(client_for, inputs, records, db, route, field, value):
    from flask_app.models import Comment
    payload = {field: value}
    if route == 'film-create':
        payload['content'] = 'Synthetic timed comment'
    response = call(client_for, inputs, route, payload)
    assert response.status_code == (201 if route == 'film-create' else 200)
    db.session.expire_all()
    stored = db.session.get(Comment, response.json['comment']['id']) if route == 'film-create' else records['point']
    assert getattr(stored, field) == value


@pytest.mark.parametrize('route', ['film-create', 'film-edit'])
@pytest.mark.parametrize('value', [None, True, 1, [], {}, 'Unknown'])
def test_comment_type_rejected(client_for, inputs, db, route, value):
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', 'comment_type': value}))


@pytest.mark.parametrize('route', ['film-create', 'film-edit'])
@pytest.mark.parametrize('value', ['Comment', 'Question', 'Highlight', 'Event'])
def test_valid_comment_types(client_for, inputs, route, value):
    response = call(client_for, inputs, route, {'content': '' if value == 'Event' else 'Synthetic',
                                              'comment_type': value})
    assert response.status_code == (201 if route == 'film-create' else 200)
    assert response.json['comment']['comment_type'] == value


@pytest.mark.parametrize('route', ['film-create', 'film-edit'])
@pytest.mark.parametrize('value', ['recipient', '__unchanged__', {}, False, 2, ['recipient', None], [1], [[]]])
def test_private_audience_rejected(client_for, inputs, db, route, value):
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', 'private_to': value}))


@pytest.mark.parametrize('route', ['film-create', 'film-edit'])
@pytest.mark.parametrize('value,expected', [(None, None), ([], []), ([' recipient ', ' '], ['recipient'])])
def test_valid_private_audience(client_for, inputs, route, value, expected):
    response = call(client_for, inputs, route, {'content': 'Synthetic', 'private_to': value})
    assert response.status_code == (201 if route == 'film-create' else 200)
    assert response.json['comment']['private_to'] == expected


@pytest.mark.parametrize('route', ['film-create', 'article-create'])
@pytest.mark.parametrize('value', [True, False, '1', 1.5, 0, -1, [], {}, 2 ** 80])
def test_parent_id_type_rejected(client_for, inputs, db, route, value):
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', 'parent_id': value}))


@pytest.mark.parametrize('route,parent,status', [
    ('film-create', 'foreign', 400), ('film-create', 'reply', 400),
    ('article-create', 'foreign_article', 400), ('article-create', 'article_reply', 400),
    ('film-create', None, 404), ('article-create', None, 404),
])
def test_invalid_parent_relationship(client_for, inputs, db, route, parent, status):
    parent_id = inputs[parent].id if parent else 1000000
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', 'parent_id': parent_id}), status)


@pytest.mark.parametrize('role', ['ordinary', 'leadership', 'admin'])
@pytest.mark.parametrize('parent_kind', ['private', 'hidden', 'private-ancestor'])
def test_inaccessible_parent(client_for, inputs, records, db, role, parent_kind):
    from flask_app.models import Comment
    parent = records['private']
    if parent_kind == 'private':
        parent.author_name = 'recipient'
        parent.private_to = '[]'
    elif parent_kind == 'hidden':
        parent.game_id = records['hidden'].id
    else:
        parent.author_name = 'recipient'
        parent.private_to = '[]'
        db.session.flush()
        parent = Comment(game_id=records['game'].id, author_name=role, parent_id=parent.id,
                         content='Synthetic legacy reply', comment_type='Comment')
        db.session.add(parent)
    db.session.commit()
    path = inputs['routes']['film-create'][1]
    # Admin is the author of the hidden-game parent, so sees it but gets wrong-game 400.
    status = 400 if parent_kind == 'hidden' and role == 'admin' else 404
    rejected(db, lambda: client_for(role).post(path, json={'content': 'Synthetic', 'parent_id': parent.id}), status)


@pytest.mark.parametrize('route,parent', [('film-create', 'parent'), ('article-create', 'article')])
def test_valid_reply(client_for, inputs, route, parent):
    response = call(client_for, inputs, route, {'content': 'Synthetic reply', 'parent_id': inputs[parent].id})
    assert response.status_code == 201
    assert response.json['comment']['parent_id'] == inputs[parent].id


@pytest.mark.parametrize('role', ['admin', 'recipient'])
def test_author_or_recipient_can_reply_to_private_parent(client_for, inputs, records, role):
    path = inputs['routes']['film-create'][1]
    response = client_for(role).post(path, json={'content': 'Synthetic', 'parent_id': records['private'].id})
    assert response.status_code == 201


@pytest.mark.parametrize('point', ['foreign_point', 'missing'])
def test_comment_foreign_point(client_for, inputs, db, point):
    point_id = inputs[point].id if point != 'missing' else 1000000
    rejected(db, lambda: call(client_for, inputs, 'film-create', {'content': 'Synthetic', 'point_id': point_id}), 404)


@pytest.mark.parametrize('value', [True, '1', 1.5, [], {}, -1, 0, 2 ** 80])
def test_comment_point_id_type(client_for, inputs, db, value):
    rejected(db, lambda: call(client_for, inputs, 'film-create', {'content': 'Synthetic', 'point_id': value}))


def test_valid_comment_point(client_for, inputs, records, db):
    from flask_app.models import Comment
    response = call(client_for, inputs, 'film-create', {'content': 'Synthetic', 'point_id': records['point'].id})
    assert response.status_code == 201
    assert db.session.get(Comment, response.json['comment']['id']).point_id == records['point'].id


@pytest.mark.parametrize('route', ['film-create', 'film-edit', 'article-create', 'article-edit'])
def test_no_comment_length_limit(client_for, inputs, route):
    content = 'Synthetic <text> " \' @[recipient]\n' * 10000
    response = call(client_for, inputs, route, {'content': content})
    assert response.status_code == (201 if route.endswith('create') else 200)
    assert response.json['comment']['content'] == content.strip()


@pytest.mark.parametrize('value', ['false', 0, 1, None, [], {}])
def test_not_filmed_requires_boolean(client_for, inputs, db, value):
    rejected(db, lambda: call(client_for, inputs, 'point', {'not_filmed': value, 'timestamp_start': 25}))


@pytest.mark.parametrize('value', [True, False])
def test_valid_not_filmed(client_for, inputs, records, db, value):
    assert call(client_for, inputs, 'point', {'not_filmed': value}).status_code == 200
    db.session.refresh(records['point'])
    assert records['point'].not_filmed is value


@pytest.mark.parametrize('field', ['pull_play', 'defense_type', 'offense_faced'])
@pytest.mark.parametrize('value', [True, 1, [], {}, 'x' * 51])
def test_tactical_label_rejected(client_for, inputs, db, field, value):
    rejected(db, lambda: call(client_for, inputs, 'point', {field: value, 'timestamp_start': 25}))


@pytest.mark.parametrize('value', [None, '', 'x' * 50])
def test_valid_tactical_labels(client_for, inputs, records, db, value):
    payload = dict.fromkeys(['pull_play', 'defense_type', 'offense_faced'], value)
    assert call(client_for, inputs, 'point', payload).status_code == 200
    db.session.refresh(records['point'])
    assert all(getattr(records['point'], field) == value for field in payload)


@pytest.mark.parametrize('value,stored', [(' ' + 'x' * 50 + ' ', 'x' * 50), ('\t Synthetic \n', 'Synthetic'),
                                          ('   ', '')])
def test_padded_tactical_labels_trimmed_before_length(client_for, inputs, records, db, value, stored):
    payload = dict.fromkeys(['pull_play', 'defense_type', 'offense_faced'], value)
    assert call(client_for, inputs, 'point', payload).status_code == 200
    db.session.refresh(records['point'])
    assert all(getattr(records['point'], field) == stored for field in payload)


def test_padded_tactical_label_still_too_long(client_for, inputs, db):
    rejected(db, lambda: call(client_for, inputs, 'point', {'pull_play': ' ' + 'x' * 51 + ' '}))


def test_foreign_point_patch(admin, inputs, records, db):
    rejected(db, lambda: admin.patch(f'/film/api/games/{records["game"].id}/points/{inputs["foreign_point"].id}',
                                     json={'timestamp_start': 25}), 404)


@pytest.mark.parametrize('value', [None, False, {}, 'changes', 1, [None], [[]], ['change']])
def test_sheet_shape_rejected(client_for, inputs, db, value):
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': value}))


def change(inputs, records, **extra):
    return dict(point_id=records['point'].id, player_name=inputs['player'].name, in_point=True, **extra)


@pytest.mark.parametrize('field,value', [
    ('point_id', None), ('point_id', True), ('point_id', '1'), ('point_id', 1.5), ('point_id', 2 ** 80),
    ('player_name', None), ('player_name', []), ('player_name', {}), ('player_name', ''),
    ('player_name', 'Synthetic outside player'), ('player_name', 'Missing player'),
    ('in_point', None), ('in_point', 'false'), ('in_point', 1), ('in_point', []),
    ('sub_status', 'invalid'), ('sub_status', {}), ('sub_status', True),
    ('unknown', 'value'),
])
def test_invalid_sheet_batch_is_atomic(client_for, inputs, records, db, field, value):
    good = change(inputs, records, sub_status='off')
    bad = {**good, field: value}
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [good, bad]}))


@pytest.mark.parametrize('field', ['point_id', 'player_name', 'in_point'])
def test_missing_sheet_fields(client_for, inputs, records, db, field):
    bad = change(inputs, records)
    del bad[field]
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [bad]}))


@pytest.mark.parametrize('point', ['foreign_point', 'missing'])
def test_foreign_sheet_point_is_atomic(client_for, inputs, records, db, point):
    good = change(inputs, records)
    bad = {**good, 'point_id': inputs[point].id if point != 'missing' else 1000000}
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [good, bad]}), 404)


def test_substitution_requires_player_in_point(client_for, inputs, records, db):
    bad = {**change(inputs, records), 'in_point': False, 'sub_status': 'off'}
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [bad]}))


@pytest.mark.parametrize('sub', [None, 'off', 'on'])
def test_valid_sheet_add_remove(client_for, inputs, records, db, sub):
    good = change(inputs, records, sub_status=sub)
    response = call(client_for, inputs, 'sheet', {'changes': [good]})
    assert response.status_code == 200
    db.session.expire_all()
    assert records['point'].players == [inputs['player']]
    assert records['point'].injury_subs == ({'off': [good['player_name']] if sub == 'off' else [],
                                           'on': [good['player_name']] if sub == 'on' else []} if sub else None)
    response = call(client_for, inputs, 'sheet', {'changes': [{**good, 'in_point': False, 'sub_status': None}]})
    assert response.status_code == 200
    db.session.expire_all()
    assert records['point'].players == [] and records['point'].injury_subs is None
    assert inputs['player'] in records['game'].roster


@pytest.mark.parametrize('source', ['listed', 'point'])
@pytest.mark.parametrize('sub', [None, 'off'])
def test_sheet_listed_but_unrostered_player(client_for, inputs, records, db, source, sub):
    """Base 93636b7 behaviour: sheet rows not on the roster are editable and join the roster."""
    from flask_app.models import Point
    game, outsider = records['game'], inputs['outsider']
    if source == 'listed':
        game.player_order_data = {'players': [inputs['player'].name, outsider.name], 'separator_index': None}
    else:
        db.session.add(Point(game_id=game.id, point_index=2, players=[outsider]))
    db.session.commit()
    assert outsider not in game.roster
    good = {**change(inputs, records, sub_status=sub), 'player_name': outsider.name}
    response = call(client_for, inputs, 'sheet', {'changes': [good]})
    assert response.status_code == 200 and response.json == {'success': True}
    db.session.expire_all()
    assert records['point'].players == [outsider] and outsider in game.roster
    assert records['point'].injury_subs == ({'off': [outsider.name], 'on': []} if sub else None)
    response = call(client_for, inputs, 'sheet', {'changes': [{**good, 'in_point': False, 'sub_status': None}]})
    assert response.status_code == 200
    db.session.expire_all()
    assert records['point'].players == [] and records['point'].injury_subs is None


@pytest.mark.parametrize('name', ['Synthetic outside player', 'Synthetic listed ghost', 'Missing player'])
def test_sheet_player_outside_all_sources_is_atomic(client_for, inputs, records, db, name):
    """Names must be listed, rostered, or on a game point, and must already be Player rows."""
    from flask_app.models import Player, Point
    game = records['game']
    other_point = inputs['foreign_point']
    other_point.players.append(inputs['outsider'])  # on another game's point only
    # Listed on the sheet but with no Player row: rejected, never created.
    game.player_order_data = {'players': [inputs['player'].name, 'Synthetic listed ghost']}
    db.session.add(Point(game_id=game.id, point_index=2, players=[inputs['player']]))
    db.session.commit()
    good = change(inputs, records)
    bad = {**good, 'player_name': name}
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [good, bad]}))
    assert Player.query.filter_by(name='Synthetic listed ghost').first() is None


@pytest.mark.parametrize('value', [None, 'not a dict', {'players': 'not a list'}, {'players': [None, 3]}])
def test_sheet_tolerates_legacy_player_order(client_for, inputs, records, db, value):
    records['game'].player_order_data = value
    db.session.commit()
    assert call(client_for, inputs, 'sheet', {'changes': [change(inputs, records)]}).status_code == 200
    bad = {**change(inputs, records), 'player_name': inputs['outsider'].name}
    rejected(db, lambda: call(client_for, inputs, 'sheet', {'changes': [bad]}))


def test_empty_sheet_batch_and_point_patch(client_for, inputs, db):
    before = snapshot(db)
    assert call(client_for, inputs, 'sheet', {'changes': []}).status_code == 200
    assert call(client_for, inputs, 'point', {}).status_code == 200
    assert snapshot(db) == before


@pytest.mark.parametrize('route', BODY_ROUTES)
def test_anonymous_json_contract(anonymous, inputs, db, route):
    method, path, _ = inputs['routes'][route]
    rejected(db, lambda: getattr(anonymous, method)(path, json={}), 401)


@pytest.mark.parametrize('route', ['point', 'sheet'])
@pytest.mark.parametrize('role', ['ordinary', 'leadership'])
def test_nonadmin_json_contract(client_for, inputs, db, route, role):
    method, path, _ = inputs['routes'][route]
    rejected(db, lambda: getattr(client_for(role), method)(path, json={}), 403)


@pytest.mark.parametrize('route', ['film-edit', 'article-edit'])
def test_nonowner_edit_json_contract(client_for, inputs, db, route):
    method, path, _ = inputs['routes'][route]
    rejected(db, lambda: getattr(client_for('recipient'), method)(path, json={'content': 'Synthetic'}), 403)


@pytest.mark.parametrize('route', BODY_ROUTES)
def test_missing_resource_json_contract(client_for, inputs, db, route):
    method, path, role = inputs['routes'][route]
    # Replace the game/post scope, or the comment id for edits.
    parts = path.split('/')
    index = -1 if route.endswith('edit') else (4 if path.startswith('/film') else 2)
    parts[index] = '1000000'
    rejected(db, lambda: getattr(client_for(role), method)('/'.join(parts), json={'content': 'Synthetic'}), 404)


@pytest.mark.parametrize('kind', ['film', 'article'])
@pytest.mark.parametrize('method,role,status', [('delete', None, 401), ('delete', 'recipient', 403),
                                              ('delete', 'ordinary', 200), ('get', None, 401)])
def test_comment_read_delete_contract(client_for, inputs, db, kind, method, role, status):
    path = inputs['routes'][kind + '-edit'][1]
    if method == 'get':
        path = path.rsplit('/', 1)[0]
        status = 200 if kind == 'article' else status
    if status == 200:
        assert getattr(client_for(role), method)(path).status_code == 200
    else:
        rejected(db, lambda: getattr(client_for(role), method)(path), status)


@pytest.mark.parametrize('route', ['film-create', 'film-edit', 'article-create', 'article-edit'])
def test_unpaired_unicode_rejected_without_write(client_for, inputs, db, route):
    rejected(db, lambda: call(client_for, inputs, route, {'content': '\ud800'}))


@pytest.mark.parametrize('route', ['film-create', 'film-edit', 'article-create', 'article-edit'])
def test_valid_unicode_content(client_for, inputs, route):
    content = 'Synthetic café 🥏 אבג'
    response = call(client_for, inputs, route, {'content': content})
    assert response.status_code == (201 if route.endswith('create') else 200)
    assert response.json['comment']['content'] == content


@pytest.mark.parametrize('value', [None, True, [], {}])
def test_legacy_author_field_type(client_for, inputs, db, value):
    rejected(db, lambda: call(client_for, inputs, 'film-create', {'content': 'Synthetic', 'author_name': value}))


@pytest.mark.parametrize('reply', [False, True])
def test_existing_film_client_payload_and_session_author(client_for, inputs, reply):
    payload = {'content': 'Synthetic client', 'author_name': 'Spoofed name', 'comment_type': 'Comment'}
    if reply:
        payload['parent_id'] = inputs['parent'].id
    else:
        payload.update(timestamp=10, private_to=None)
    response = call(client_for, inputs, 'film-create', payload)
    assert response.status_code == 201
    assert response.json['comment']['author_name'] == 'ordinary'


@pytest.mark.parametrize('route', BODY_ROUTES)
def test_oversized_url_id_rejected(client_for, inputs, db, route):
    method, path, role = inputs['routes'][route]
    parts = path.split('/')
    parts[4 if path.startswith('/film') else 2] = str(2 ** 80)
    rejected(db, lambda: getattr(client_for(role), method)('/'.join(parts), json={}))


@pytest.mark.parametrize('route', ['film-edit', 'article-edit'])
@pytest.mark.parametrize('field', ['parent_id', 'point_id', 'timestamp'])
def test_edit_cannot_reassign_relationships(client_for, inputs, db, route, field):
    rejected(db, lambda: call(client_for, inputs, route, {'content': 'Synthetic', field: 1}))


@pytest.mark.parametrize('route', BODY_ROUTES)
def test_unparseable_json_nesting(client_for, inputs, db, route):
    body = '{"content":' + '[' * 1500 + '0' + ']' * 1500 + '}'
    rejected(db, lambda: call(client_for, inputs, route, data=body, content_type='application/json'))
