"""Tests for articles routes, article comments, and article notifications."""
import json
from flask_app import db
from flask_app.models import Post, ArticleComment, ArticleCommentNotification
from tests.conftest import make_admin, make_user, login_as


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_post(title='Test Post', author='Tester', content='Hello world'):
    p = Post(title=title, author=author, content=content)
    db.session.add(p)
    db.session.commit()
    return p


# ── Index ─────────────────────────────────────────────────────────────────────

def test_index_200(client):
    rv = client.get('/')
    assert rv.status_code == 200


# ── Single post ───────────────────────────────────────────────────────────────

def test_post_200(client):
    p = make_post()
    rv = client.get(f'/post/{p.id}')
    assert rv.status_code == 200


def test_post_404(client):
    rv = client.get('/post/99999')
    assert rv.status_code == 404


# ── New post ──────────────────────────────────────────────────────────────────

def test_new_post_as_admin_creates_post(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    rv = client.post(
        '/new_post',
        data={'title': 'My Title', 'author': 'Admin', 'content': 'Body text'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert Post.query.filter_by(title='My Title').first() is not None


def test_new_post_as_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.post(
        '/new_post',
        data={'title': 'My Title', 'author': 'Alice', 'content': 'Body'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    assert Post.query.count() == 0


# ── Edit post ─────────────────────────────────────────────────────────────────

def test_edit_post_updates_fields(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    p = make_post()
    rv = client.post(
        f'/post/{p.id}/edit',
        data={
            'title': 'Updated Title',
            'author': 'Editor',
            'content': 'New content',
            'created_at': '2024-06-01',
        },
        follow_redirects=False,
    )
    assert rv.status_code == 302
    db.session.refresh(p)
    assert p.title == 'Updated Title'
    assert p.author == 'Editor'


def test_edit_post_non_admin_redirects(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    p = make_post()
    rv = client.post(
        f'/post/{p.id}/edit',
        data={'title': 'X', 'author': 'X', 'content': 'X', 'created_at': '2024-01-01'},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    db.session.refresh(p)
    assert p.title == 'Test Post'  # unchanged


# ── Delete post ───────────────────────────────────────────────────────────────

def test_delete_post_as_admin(client):
    make_admin()
    login_as(client, 'Admin', 'adminpass')
    p = make_post()
    rv = client.post(f'/post/{p.id}/delete', follow_redirects=False)
    assert rv.status_code == 302
    assert Post.query.get(p.id) is None


# ── Article comments API ──────────────────────────────────────────────────────

def test_get_article_comments_returns_list(client):
    p = make_post()
    rv = client.get(f'/post/{p.id}/comments')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'comments' in data
    assert isinstance(data['comments'], list)


def test_create_article_comment_unauthenticated(client):
    p = make_post()
    rv = client.post(
        f'/post/{p.id}/comments',
        json={'content': 'Hello'},
    )
    assert rv.status_code == 401


def test_create_article_comment_authenticated(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    p = make_post()
    rv = client.post(
        f'/post/{p.id}/comments',
        json={'content': 'Great post!'},
    )
    assert rv.status_code == 201
    data = rv.get_json()
    assert data['comment']['author_name'] == 'Alice'
    assert data['comment']['content'] == 'Great post!'


def test_create_article_comment_reply_creates_notification(client):
    """Reply to a comment creates a 'reply' notification for the parent author."""
    author = make_user('Bob')
    replier = make_user('Carol')
    p = make_post()
    # Bob creates a top-level comment
    parent = ArticleComment(post_id=p.id, author_name='Bob', content='Parent')
    db.session.add(parent)
    db.session.commit()

    # Carol logs in and replies
    login_as(client, 'Carol', 'userpass')
    rv = client.post(
        f'/post/{p.id}/comments',
        json={'content': 'Reply here', 'parent_id': parent.id},
    )
    assert rv.status_code == 201
    notif = ArticleCommentNotification.query.filter_by(
        recipient_username='Bob', notification_type='reply'
    ).first()
    assert notif is not None


def test_edit_article_comment_by_author(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    p = make_post()
    c = ArticleComment(post_id=p.id, author_name='Alice', content='Original')
    db.session.add(c)
    db.session.commit()

    rv = client.patch(
        f'/post/{p.id}/comments/{c.id}',
        json={'content': 'Updated'},
    )
    assert rv.status_code == 200
    db.session.refresh(c)
    assert c.content == 'Updated'


def test_edit_article_comment_by_non_author(client):
    make_user('Alice')
    make_user('Bob')
    p = make_post()
    c = ArticleComment(post_id=p.id, author_name='Alice', content='Original')
    db.session.add(c)
    db.session.commit()

    login_as(client, 'Bob', 'userpass')
    rv = client.patch(
        f'/post/{p.id}/comments/{c.id}',
        json={'content': 'Hijacked'},
    )
    assert rv.status_code == 403


def test_delete_article_comment_by_admin(client):
    """Admin can delete anyone's article comment."""
    make_admin()
    make_user()
    p = make_post()
    c = ArticleComment(post_id=p.id, author_name='Alice', content='Comment')
    db.session.add(c)
    db.session.commit()

    login_as(client, 'Admin', 'adminpass')
    rv = client.delete(f'/post/{p.id}/comments/{c.id}')
    assert rv.status_code == 200
    assert ArticleComment.query.get(c.id) is None


# ── Article notifications API ─────────────────────────────────────────────────

def test_get_article_notifications_unauthenticated(client):
    rv = client.get('/api/article-notifications')
    assert rv.status_code == 401


def test_get_article_notifications_returns_data(client):
    make_user()
    login_as(client, 'Alice', 'userpass')
    rv = client.get('/api/article-notifications')
    assert rv.status_code == 200
    data = rv.get_json()
    assert 'notifications' in data
    assert 'unread_count' in data


def test_mark_article_notification_read(client):
    make_user()
    p = make_post()
    c = ArticleComment(post_id=p.id, author_name='Alice', content='Hi')
    db.session.add(c)
    db.session.flush()
    notif = ArticleCommentNotification(
        recipient_username='Alice',
        comment_id=c.id,
        post_id=p.id,
        notification_type='reply',
        is_read=False,
    )
    db.session.add(notif)
    db.session.commit()

    login_as(client, 'Alice', 'userpass')
    rv = client.post(f'/api/article-notifications/{notif.id}/read')
    assert rv.status_code == 200
    db.session.refresh(notif)
    assert notif.is_read is True
    assert notif.read_at is not None


def test_mark_all_article_notifications_read(client):
    make_user()
    p = make_post()
    c = ArticleComment(post_id=p.id, author_name='Alice', content='Hi')
    db.session.add(c)
    db.session.flush()
    for _ in range(3):
        db.session.add(ArticleCommentNotification(
            recipient_username='Alice',
            comment_id=c.id,
            post_id=p.id,
            notification_type='thread',
            is_read=False,
        ))
    db.session.commit()

    login_as(client, 'Alice', 'userpass')
    rv = client.post('/api/article-notifications/read-all')
    assert rv.status_code == 200
    unread = ArticleCommentNotification.query.filter_by(
        recipient_username='Alice', is_read=False
    ).count()
    assert unread == 0
