"""T02: logs and stdout must not contain credentials or private content."""
import logging
import os

import pytest

WRONG_PASSWORD = 'synthetic-wrong-password-T02'
UNKNOWN_USER = 'synthetic-unknown-user-T02'
PRIVATE_BODY = 'synthetic-private-body-T02'
POST_BODY = 'synthetic-post-body-T02'
POST_TITLE = 'synthetic-post-title-T02'


def _output(caplog, capsys):
    captured = capsys.readouterr()
    return caplog.text + captured.out + captured.err


def _assert_clean(caplog, capsys, *secrets):
    text = _output(caplog, capsys)
    for secret in secrets:
        assert secret not in text


def test_failed_login_unknown_user(anonymous, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    response = anonymous.post('/login', data={'username': UNKNOWN_USER, 'password': WRONG_PASSWORD})
    assert response.status_code == 302
    _assert_clean(caplog, capsys, WRONG_PASSWORD, UNKNOWN_USER)
    assert 'login_failed reason=unknown_user' in caplog.text


def test_failed_login_wrong_password(anonymous, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    response = anonymous.post('/login', data={'username': 'ordinary', 'password': WRONG_PASSWORD})
    assert response.status_code == 302
    _assert_clean(caplog, capsys, WRONG_PASSWORD, 'ordinary')
    assert 'login_failed reason=bad_password' in caplog.text


def test_login_password_not_configured(anonymous, monkeypatch, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    monkeypatch.delenv('FILM_USER_PASSWORD')
    anonymous.post('/login', data={'username': 'ordinary', 'password': WRONG_PASSWORD})
    _assert_clean(caplog, capsys, WRONG_PASSWORD)
    assert 'password_not_configured' in caplog.text


def test_successful_login_does_not_log_password(anonymous, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    password = os.environ['FILM_USER_PASSWORD']
    response = anonymous.post('/login', data={'username': 'ordinary', 'password': password})
    assert response.status_code == 302
    with anonymous.session_transaction() as session:
        assert 'user_id' in session
    _assert_clean(caplog, capsys, password, password.lower())


@pytest.mark.parametrize('private', [True, False])
def test_comment_notifications_do_not_log_body(leadership, records, caplog, capsys, private):
    caplog.set_level(logging.DEBUG)
    body = {'content': f'{PRIVATE_BODY} @[recipient]'}
    if private:
        body['private_to'] = ['recipient']
    response = leadership.post(f'/film/api/games/{records["game"].id}/comments', json=body)
    assert response.status_code in (200, 201)
    _assert_clean(caplog, capsys, PRIVATE_BODY, 'recipient')
    assert 'comment_notifications_created' in caplog.text


def test_everyone_mention_does_not_log_body(leadership, records, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    response = leadership.post(f'/film/api/games/{records["game"].id}/comments',
                               json={'content': f'{PRIVATE_BODY} @[Everyone]'})
    assert response.status_code in (200, 201)
    _assert_clean(caplog, capsys, PRIVATE_BODY)


def test_new_post_does_not_print_content(admin, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    response = admin.post('/new_post', data={'title': POST_TITLE, 'author': 'admin', 'content': POST_BODY})
    assert response.status_code == 302
    _assert_clean(caplog, capsys, POST_TITLE, POST_BODY)
