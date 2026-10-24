"""Desired invariants; only the specific final assertion may expected-fail."""
import json

import pytest

pytestmark = pytest.mark.known_failure


class AuditRegression(AssertionError):
    """Distinguishes the audited invariant from setup or unrelated failures."""


def require(condition, message):
    if not condition:
        raise AuditRegression(message)


@pytest.mark.parametrize('suffix', ['', '/comments'])
@pytest.mark.xfail(strict=True, raises=AuditRegression, reason='T03: alternate API exposes private comments')
def test_alternate_api_hides_private_comments(ordinary, records, suffix):
    response = ordinary.get(f'/api/v1/games/{records["game"].id}{suffix}')
    assert response.status_code == 200
    payload = response.json['game'] if not suffix else response.json
    require(records['private'].id not in {c['id'] for c in payload['comments']},
            'Nonrecipient received private comment')


@pytest.mark.xfail(strict=True, raises=AuditRegression, reason='T03: hidden player page accessible directly')
def test_hidden_game_denied_directly(ordinary, records):
    response = ordinary.get(f'/film/games/{records["hidden"].id}')
    assert response.status_code in (200, 403, 404)
    require(response.status_code in (403, 404), 'Hidden game returned to nonadmin')


@pytest.mark.xfail(strict=True, raises=AuditRegression, reason='T03: private reply leaks through parent notification')
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
    notifications = ordinary.get('/film/api/notifications')
    assert notifications.status_code == 200
    require(all(n['comment_id'] != response.json['comment']['id']
                for n in notifications.json['notifications']), 'Nonrecipient notified of private reply')


@pytest.mark.parametrize('invalid', ['timestamp', 'parent_id'])
@pytest.mark.xfail(strict=True, raises=AuditRegression, reason='T04: invalid timestamp/cross-game parent accepted')
def test_invalid_comment_rejected_without_write(ordinary, records, db, invalid):
    from flask_app.models import Comment
    payload = {'content': 'Synthetic invalid comment'}
    if invalid == 'timestamp':
        payload['timestamp'] = 'not-a-number'
    else:
        parent = Comment(game_id=records['hidden'].id, author_name='ordinary',
                         content='Synthetic other-game parent', comment_type='Comment')
        db.session.add(parent)
        db.session.commit()
        payload['parent_id'] = parent.id
    before = Comment.query.count()
    response = ordinary.post(f'/film/api/games/{records["game"].id}/comments', json=payload)
    assert response.status_code in (201, 400, 404, 422)
    require(response.status_code in (400, 404, 422) and Comment.query.count() == before,
            'Invalid comment accepted or persisted')


@pytest.mark.xfail(strict=True, raises=AuditRegression, reason='T09: string beacon content type returns 500')
def test_string_beacon_does_not_return_server_error(ordinary, records):
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=json.dumps({'seconds_watched': 10, 'playback_position': 40}),
                             content_type='text/plain;charset=UTF-8')
    assert response.is_json
    assert response.status_code in (200, 400, 415, 500)
    require(response.status_code != 500, 'String beacon becomes internal server error')
