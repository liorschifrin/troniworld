"""Desired invariants; only the specific final assertion may expected-fail."""
import json

import pytest


class AuditRegression(AssertionError):
    """Distinguishes the audited invariant from setup or unrelated failures."""


def require(condition, message):
    if not condition:
        raise AuditRegression(message)


@pytest.mark.parametrize('invalid', ['timestamp', 'parent_id'])
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


def test_string_beacon_does_not_return_server_error(ordinary, records):
    # T09: a text/plain beacon body (older cached pages) used to become a 500.
    response = ordinary.post(f'/film/api/games/{records["game"].id}/track-watch-time',
                             data=json.dumps({'seconds_watched': 10, 'playback_position': 40}),
                             content_type='text/plain;charset=UTF-8')
    assert response.is_json
    assert response.status_code in (200, 400, 415)
