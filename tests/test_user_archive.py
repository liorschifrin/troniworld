"""T08a: deleting a user archives the account and keeps every record."""
from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from flask_app.models import (
    ArticleComment, ArticleCommentNotification, Comment, CommentNotification, GameWatched,
    LoginEvent, Post, User, VideoWatchSession,
)

TABLES = (Comment, CommentNotification, ArticleComment, ArticleCommentNotification,
          LoginEvent, VideoWatchSession, GameWatched)


@pytest.fixture
def history(db, records):
    """Synthetic history for the ordinary user: logins, watching, comments, replies, tags."""
    user = records['users']['ordinary']
    game = records['game']
    admin_comment = Comment(game_id=game.id, author_name='admin', content='Synthetic tag @[ordinary]',
                            comment_type='Comment')
    own = Comment(game_id=game.id, author_name='ordinary', content='Synthetic own comment', comment_type='Comment')
    db.session.add_all([admin_comment, own])
    db.session.flush()
    reply_to_own = Comment(game_id=game.id, author_name='leadership', content='Synthetic reply to ordinary',
                           comment_type='Comment', parent_id=own.id)
    own_reply = Comment(game_id=game.id, author_name='ordinary', content='Synthetic own reply',
                        comment_type='Comment', parent_id=admin_comment.id)
    post = Post(title='Synthetic', author='admin', content='<p>Synthetic</p>')
    db.session.add_all([reply_to_own, own_reply, post])
    db.session.flush()
    article = ArticleComment(post_id=post.id, author_name='ordinary', content='Synthetic article comment')
    db.session.add(article)
    db.session.flush()
    db.session.add_all([
        LoginEvent(user_id=user.id), LoginEvent(user_id=user.id),
        VideoWatchSession(user_id=user.id, game_id=game.id, watch_duration_seconds=30),
        GameWatched(user_id=user.id, game_id=game.id),
        CommentNotification(recipient_username='ordinary', comment_id=admin_comment.id, game_id=game.id,
                            notification_type='mention'),
        CommentNotification(recipient_username='admin', comment_id=reply_to_own.id, game_id=game.id,
                            notification_type='mention', is_read=True),
        ArticleCommentNotification(recipient_username='ordinary', comment_id=article.id, post_id=post.id,
                                   notification_type='reply'),
    ])
    db.session.commit()
    return user


def snapshot(db):
    return {model.__name__: sorted(
        tuple((c.name, str(getattr(row, c.name))) for c in model.__table__.columns) for row in db.session.query(model))
        for model in TABLES}


def archive(client, user):
    return client.post('/admin/users', data={'action': 'archive', 'user_id': str(user.id)})


def test_hard_delete_with_login_records_is_the_reproduced_failure(db, history):
    """Documents why deletion cannot be a row delete: login events block it."""
    db.session.delete(history)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_archive_user_with_login_and_watch_records_succeeds(admin, db, history):
    response = archive(admin, history)
    assert response.status_code == 302
    user = db.session.get(User, history.id)
    assert user is not None and user.archived_at is not None and user.is_archived
    assert db.session.query(LoginEvent).filter_by(user_id=user.id).count() == 2
    assert db.session.query(GameWatched).filter_by(user_id=user.id).count() == 1
    assert db.session.query(VideoWatchSession).filter_by(user_id=user.id).count() == 1


def test_archive_changes_no_comment_reply_notification_or_tag(admin, db, history):
    before = snapshot(db)
    assert before['Comment'] and before['CommentNotification'] and before['ArticleComment']
    assert archive(admin, history).status_code == 302
    db.session.expire_all()
    assert snapshot(db) == before


def test_deleted_form_action_is_gone(admin, db, history):
    admin.post('/admin/users', data={'action': 'delete', 'user_id': str(history.id)})
    assert db.session.get(User, history.id).archived_at is None


def test_archived_user_cannot_log_in(anonymous, db, history, admin):
    archive(admin, history)
    before = db.session.query(LoginEvent).count()
    response = anonymous.post('/login', data={'username': 'ordinary', 'password': 'synthetic-member-password'})
    assert response.status_code == 302 and '/login' in response.headers['Location']
    with anonymous.session_transaction() as session:
        assert 'user_id' not in session
    assert db.session.query(LoginEvent).count() == before


def test_active_user_can_still_log_in(anonymous, db, history):
    response = anonymous.post('/login', data={'username': 'ordinary', 'password': 'synthetic-member-password'})
    assert response.status_code == 302
    with anonymous.session_transaction() as session:
        assert session['user_id'] == history.id


def test_existing_session_of_archived_user_cannot_act(ordinary, admin, db, records, history):
    game = records['game']
    assert ordinary.get(f'/film/api/games/{game.id}/comments').status_code == 200
    archive(admin, history)
    response = ordinary.post(f'/film/api/games/{game.id}/comments', json={'content': 'Synthetic after archive'})
    assert response.status_code == 401
    assert ordinary.get(f'/film/api/games/{game.id}/comments').status_code == 401
    assert ordinary.post(f'/film/api/games/{game.id}/toggle-watched').status_code in (302, 401)
    assert db.session.query(Comment).filter_by(content='Synthetic after archive').count() == 0
    assert db.session.query(GameWatched).filter_by(user_id=history.id).count() == 1


@pytest.mark.parametrize('name', ['ordinary', 'Ordinary', 'ORDINARY'])
def test_archived_username_cannot_be_registered(admin, db, history, name):
    archive(admin, history)
    count = db.session.query(User).count()
    response = admin.post('/register', data={'username': name})
    assert response.status_code == 302
    assert db.session.query(User).count() == count
    assert db.session.query(User).filter_by(id=history.id).one().hashed_password == 'synthetic-unused-hash'


def test_archived_username_cannot_be_created_by_admin(admin, db, history):
    archive(admin, history)
    count = db.session.query(User).count()
    response = admin.post('/admin/users', data={'action': 'create', 'username': 'Ordinary'}, follow_redirects=True)
    assert 'archived and reserved' in response.text
    assert db.session.query(User).count() == count


def test_active_username_cannot_be_reassigned(admin, db, history):
    count = db.session.query(User).count()
    admin.post('/admin/users', data={'action': 'create', 'username': 'ordinary'})
    admin.post('/register', data={'username': 'ordinary'})
    assert db.session.query(User).count() == count
    assert db.session.get(User, history.id).hashed_password == 'synthetic-unused-hash'


def test_archived_user_is_not_relinked_or_recreated_for_a_player(db, app, history, records):
    from flask_app.film_routes import link_or_create_user_for_player
    from flask_app.models import Player
    history.archived_at = datetime.utcnow()
    player = Player(name='ordinary')
    db.session.add(player)
    db.session.flush()
    count = db.session.query(User).count()
    link_or_create_user_for_player(player)
    assert history.player_id is None and db.session.query(User).count() == count


def test_admin_cannot_archive_self(admin, db, records):
    me = records['users']['admin']
    archive(admin, me)
    assert db.session.get(User, me.id).archived_at is None


def test_admin_can_archive_another_admin(admin, db):
    other = User(username='other_admin', hashed_password='x', is_admin=True)
    db.session.add(other)
    db.session.commit()
    assert archive(admin, other).status_code == 302
    assert db.session.get(User, other.id).is_archived


def test_archiving_twice_keeps_first_timestamp(admin, db, history):
    archive(admin, history)
    first = db.session.get(User, history.id).archived_at
    archive(admin, history)
    db.session.expire_all()
    assert db.session.get(User, history.id).archived_at == first


def test_archived_user_cannot_have_roles_toggled(admin, db, history):
    archive(admin, history)
    response = admin.post('/admin/users', data={'action': 'toggle_role', 'user_id': str(history.id),
                                                'role_type': 'leadership'},
                          headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 400
    assert db.session.get(User, history.id).is_leadership is False


def test_admin_page_labels_archived_users(admin, db, history):
    assert 'Archived' not in admin.get('/admin/users').text.replace('Archive</button>', '')
    archive(admin, history)
    page = admin.get('/admin/users').text
    assert 'user-archived-tag' in page and 'ordinary' in page
    assert 'value="archive"' not in page.split('ordinary', 1)[1].split('</tr>', 1)[0]


def test_archived_user_gets_no_new_everyone_notification(admin, db, history, records, leadership):
    archive(admin, history)
    before = db.session.query(CommentNotification).filter_by(recipient_username='ordinary').count()
    response = leadership.post(f'/film/api/games/{records["game"].id}/comments',
                               json={'content': 'Synthetic @[Everyone]'})
    assert response.status_code == 201
    assert db.session.query(CommentNotification).filter_by(recipient_username='ordinary').count() == before


def test_archived_username_hidden_from_login_suggestions(anonymous, admin, history):
    archive(admin, history)
    assert 'ordinary' not in anonymous.get('/login').text
