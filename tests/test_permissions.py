from urllib.parse import urlsplit

import pytest


@pytest.mark.parametrize('path', ['/film/games', '/film/api/games/1/comments'])
def test_anonymous_requires_login(anonymous, path):
    response = anonymous.get(path)
    if '/api/' in path:
        assert response.status_code == 401 and response.is_json
    else:
        assert response.status_code == 302
        assert urlsplit(response.location).path == '/login'


@pytest.mark.parametrize('role', ['ordinary', 'leadership'])
def test_nonadmin_cannot_change_point(client_for, records, db, role):
    point = records['point']
    response = client_for(role).patch(
        f'/film/api/games/{records["game"].id}/points/{point.id}',
        json={'timestamp_start': 999},
    )
    assert response.status_code == 403 and response.is_json
    db.session.refresh(point)
    assert point.timestamp_start == 10


def test_admin_can_change_point(admin, records, db):
    point = records['point']
    response = admin.patch(f'/film/api/games/{records["game"].id}/points/{point.id}',
                           json={'timestamp_start': 20})
    assert response.status_code == 200
    db.session.refresh(point)
    assert point.timestamp_start == 20


@pytest.mark.parametrize('role', ['ordinary', 'leadership'])
def test_nonowner_cannot_delete_comment(client_for, records, db, role):
    from flask_app.models import Comment
    comment = records['private']
    response = client_for(role).delete(
        f'/film/api/games/{records["game"].id}/comments/{comment.id}')
    assert response.status_code == 403
    assert db.session.get(Comment, comment.id) is not None


@pytest.mark.parametrize('role,visible', [('ordinary', False), ('recipient', True), ('admin', True)])
def test_main_api_private_comment_visibility(client_for, records, role, visible):
    response = client_for(role).get(f'/film/api/games/{records["game"].id}/comments')
    assert response.status_code == 200
    ids = {comment['id'] for comment in response.json['comments']}
    assert (records['private'].id in ids) is visible


def test_hidden_game_omitted_from_member_list(ordinary, records):
    response = ordinary.get('/film/games')
    assert response.status_code == 200
    assert records['game'].title in response.text
    assert records['hidden'].title not in response.text


def test_schema_is_fresh_and_foreign_keys_enabled(db):
    from flask_app.models import User
    from sqlalchemy import text
    assert User.query.count() == 0
    assert db.session.execute(text('PRAGMA foreign_keys')).scalar() == 1


def test_upload_stays_in_temporary_directory(admin, app):
    from io import BytesIO
    from pathlib import Path
    from conftest import synthetic_image
    response = admin.post('/upload_image', data={'upload': (BytesIO(synthetic_image()), 'test.png')})
    assert response.status_code == 201
    files = list(Path(app.config['UPLOAD_FOLDER']).iterdir())
    assert len(files) == 1
    assert files[0].read_bytes() == synthetic_image()
