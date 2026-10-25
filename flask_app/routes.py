from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
import logging
import os

from .uploads import UPLOAD_URL_PREFIX, UploadError, save_image
from .sanitize import has_visible_content, removed_content, sanitize_html
from . import app, db
from .models import Post, User, LoginEvent, ArticleComment, ArticleCommentNotification

from .csrf import clear_token as clear_csrf_token
from .utils import get_current_user
from .input_validation import json_api, json_object, optional_id, text_value

logger = logging.getLogger(__name__)

@app.route('/')
def index():
    current_user = get_current_user()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('articles/index.html', current_user=current_user, posts=posts)


@app.route('/register', methods=['GET', 'POST'])
def register():
    # If an admin account already exists, redirect to login unless admin is logged in. Otherwise, allow registration.
    admin_existing = User.query.filter_by(is_admin=True).first()
    if admin_existing:
        current_user = get_current_user()
        if not current_user:
            return redirect(url_for('login'))
        if not current_user or not current_user.is_admin:
            return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().capitalize()
        is_admin = request.form.get('is_admin', '0') == '1'

        if not username:
            flash('Username is required.')
            return redirect(url_for('register'))

        existing = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing:
            flash('Username already exists.')
            return redirect(url_for('register'))

        # Get the appropriate shared password based on role
        if is_admin:
            password = os.getenv('FILM_ADMIN_PASSWORD')
        else:
            password = os.getenv('FILM_USER_PASSWORD')
        
        if not password:
            flash('Shared passwords not configured in .env file.')
            return redirect(url_for('register'))

        user = User(
            username=username,
            hashed_password=generate_password_hash(password.lower()),
            is_admin=is_admin,
        )
        db.session.add(user)
        db.session.commit()
        session.permanent = True
        clear_csrf_token()
        session['user_id'] = user.id
        flash('Registration successful.')
        return redirect(url_for('index'))

    return render_template('articles/register.html')


def _login_template(next_url):
    """Pick the right login template based on where the user is coming from."""
    from urllib.parse import urlparse
    parsed = urlparse(next_url)
    path = parsed.path if (next_url and not parsed.scheme and not parsed.netloc) else ''
    # Film/admin pages → dark film-room login
    if path.startswith('/film') or path.startswith('/admin'):
        return 'film_room/pages/login.html'
    # Articles pages (index, /post/*, /new_post, /edit_post) → editorial login
    return 'articles/login_articles.html'


@app.route('/login', methods=['GET', 'POST'])
def login():
    from urllib.parse import urlparse

    # Determine next destination from query-string (GET) or hidden field (POST)
    raw_next = request.args.get('next', '') or request.form.get('next_hidden', '')
    parsed = urlparse(raw_next)
    next_url = raw_next if (raw_next and not parsed.scheme and not parsed.netloc) else ''

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip().lower()

        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if not user:
            logger.warning("login_failed reason=unknown_user")
            flash('Invalid username or password.')
            return redirect(url_for('login', next=raw_next) if raw_next else url_for('login'))
        
        # Check password against shared passwords based on role
        if user.is_admin or user.is_leadership:
            expected_password = os.getenv('FILM_ADMIN_PASSWORD')
        else:
            expected_password = os.getenv('FILM_USER_PASSWORD')
        
        if not expected_password:
            logger.error("login_failed reason=password_not_configured user_id=%s", user.id)
            flash('Authentication system not configured properly.')
            return redirect(url_for('login', next=raw_next) if raw_next else url_for('login'))
        
        # Verify entered password matches the expected shared password for this role
        if password != expected_password.lower():
            logger.warning("login_failed reason=bad_password user_id=%s", user.id)
            flash('Invalid username or password.')
            return redirect(url_for('login', next=raw_next) if raw_next else url_for('login'))

        session.permanent = True
        clear_csrf_token()
        session['user_id'] = user.id
        
        # Track login event
        login_event = LoginEvent(user_id=user.id)
        db.session.add(login_event)
        db.session.commit()
        
        flash('Logged in.')
        
        # Redirect back to originating page, defaulting by context
        if next_url:
            return redirect(next_url)
        parsed_next = urlparse(raw_next)
        path = parsed_next.path if raw_next else ''
        if path.startswith('/film') or path.startswith('/admin'):
            return redirect(url_for('games_list'))
        return redirect(url_for('index'))

    template = _login_template(next_url)
    all_usernames = [u.username for u in User.query.order_by(User.username).all()]
    return render_template(template, next=next_url, all_usernames=all_usernames)


@app.route('/post/<int:post_id>', methods=['GET'])
def post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    return render_template('articles/post.html', post=post, current_user=current_user)


CONTENT_DISALLOWED = 'Content contained only disallowed markup.'
CONTENT_ALTERED = 'Some markup in the content is not allowed and was removed. Check the post.'


def _submitted_post_content():
    """Sanitize the submitted article HTML; return (content, altered).

    content is '' when nothing visible (text or image) survives; altered is
    True when sanitizing removed text or markup.
    """
    raw = request.form.get('content', '')
    content = sanitize_html(raw).strip()
    altered = removed_content(raw, content)
    return (content if has_visible_content(content) else ''), altered


@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return redirect(url_for('index'))

    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        content, altered = _submitted_post_content()
        created_at_str = request.form.get('created_at', '').strip()

        if not content and altered:
            flash(CONTENT_DISALLOWED)
            return redirect(url_for('edit_post', post_id=post_id))
        if not title or not author or not content or not created_at_str:
            flash('Title, author, content, and date are required.')
            return redirect(url_for('edit_post', post_id=post_id))

        # Parse the datetime string
        from datetime import datetime
        try:
            created_at = datetime.strptime(created_at_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format.')
            return redirect(url_for('edit_post', post_id=post_id))

        post.title = title
        post.author = author
        post.content = content
        post.created_at = created_at
        db.session.commit()
        flash('Post updated.')
        if altered:
            flash(CONTENT_ALTERED)
        return redirect(url_for('post', post_id=post_id))

    # The editor loads what a save would store, escaped inside the textarea.
    return render_template('articles/edit_post.html', post=post, editor_content=sanitize_html(post.content))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
def delete_post(post_id):
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return redirect(url_for('index'))

    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully.')
    return redirect(url_for('index'))


# ── Article Comments API ────────────────────────────────────────────────────

from zoneinfo import ZoneInfo as _ZI
from datetime import timezone as _tz, datetime as _datetime
_EST = _ZI('America/New_York')

def _fmt_est(dt):
    if not dt:
        return ''
    return dt.replace(tzinfo=_tz.utc).astimezone(_EST).strftime('%b %d, %Y %I:%M %p')


def _create_article_notifs(comment, post_id, author_username):
    """Create reply/thread notifications for article comment replies."""
    if not comment.parent_id:
        return  # top-level comments don't trigger notifications

    scores = {'reply': 2, 'thread': 1}
    priority = {}

    def _set(uname, ntype):
        if uname == author_username:
            return
        if scores.get(ntype, 0) > scores.get(priority.get(uname, ''), 0):
            priority[uname] = ntype

    # Parent author gets a 'reply' notification
    parent = ArticleComment.query.get(comment.parent_id)
    if parent:
        _set(parent.author_name, 'reply')

    # Other users who replied in the same thread get a 'thread' notification
    siblings = ArticleComment.query.filter(
        ArticleComment.parent_id == comment.parent_id,
        ArticleComment.id != comment.id
    ).all()
    for s in siblings:
        _set(s.author_name, 'thread')

    now = _datetime.utcnow()
    for uname, ntype in priority.items():
        notif = ArticleCommentNotification(
            recipient_username=uname,
            comment_id=comment.id,
            post_id=post_id,
            notification_type=ntype,
            is_read=False,
            created_at=now,
        )
        db.session.add(notif)
    db.session.commit()

def _serialize_article_comment(c):
    replies = [{
        'id': r.id,
        'author_name': r.author_name,
        'content': r.content,
        'created_at': _fmt_est(r.created_at),
        'parent_id': r.parent_id,
    } for r in c.replies.order_by(ArticleComment.created_at).all()]
    return {
        'id': c.id,
        'author_name': c.author_name,
        'content': c.content,
        'created_at': _fmt_est(c.created_at),
        'parent_id': c.parent_id,
        'replies': replies,
    }

@app.route('/post/<int:post_id>/comments', methods=['GET'])
@json_api(public=True)
def get_article_comments(post_id):
    Post.query.get_or_404(post_id)
    top_level = ArticleComment.query.filter_by(post_id=post_id, parent_id=None)\
        .order_by(ArticleComment.created_at).all()
    return jsonify({'comments': [_serialize_article_comment(c) for c in top_level]})

@app.route('/post/<int:post_id>/comments', methods=['POST'])
@json_api()
def create_article_comment(post_id):
    current_user = get_current_user()
    Post.query.get_or_404(post_id)
    data = json_object({'content', 'parent_id'})
    content = text_value(data.get('content', ''), 'content')
    parent_id = optional_id(data.get('parent_id'), 'parent_id')
    if parent_id is not None:
        parent = db.session.get(ArticleComment, parent_id)
        if parent is None:
            raise NotFound()
        if parent.post_id != post_id:
            raise BadRequest('Parent must belong to this post')
        if parent.parent_id is not None:
            raise BadRequest('Replies may only target top-level comments')
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    c = ArticleComment(
        post_id=post_id,
        parent_id=parent_id,
        author_name=current_user.username,
        content=content,
    )
    db.session.add(c)
    db.session.commit()
    _create_article_notifs(c, post_id, current_user.username)
    return jsonify({'success': True, 'comment': _serialize_article_comment(c)}), 201

@app.route('/post/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
@json_api()
def delete_article_comment(post_id, comment_id):
    current_user = get_current_user()
    c = ArticleComment.query.filter_by(id=comment_id, post_id=post_id).first_or_404()
    if not current_user.is_admin and c.author_name != current_user.username:
        return jsonify({'error': 'Unauthorized'}), 403
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/post/<int:post_id>/comments/<int:comment_id>', methods=['PATCH'])
@json_api()
def edit_article_comment(post_id, comment_id):
    current_user = get_current_user()
    c = ArticleComment.query.filter_by(id=comment_id, post_id=post_id).first_or_404()
    if c.author_name != current_user.username:
        return jsonify({'error': 'Unauthorized'}), 403
    data = json_object({'content'})
    content = text_value(data.get('content', ''), 'content')
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    c.content = content
    db.session.commit()
    return jsonify({'success': True, 'comment': _serialize_article_comment(c)})


@app.route('/new_post', methods=['GET', 'POST'])
def new_post():    
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        content, altered = _submitted_post_content()

        if not content and altered:
            flash(CONTENT_DISALLOWED)
            return redirect(url_for('new_post'))
        if not title or not author or not content:
            flash('Title, author, and content are required.')
            return redirect(url_for('new_post'))

        post = Post(title=title, author=author, content=content)
        db.session.add(post)
        db.session.commit()
        flash('Post created.')
        if altered:
            flash(CONTENT_ALTERED)
        return redirect(url_for('index'))

    return render_template('articles/new_post.html', current_user=current_user)


@app.route('/upload_image', methods=['POST'])
def upload_image():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    if 'upload' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    try:
        unique_name = save_image(request.files['upload'], app.config['UPLOAD_FOLDER'])
    except UploadError as error:
        return jsonify({'error': error.message}), error.status

    public_url = f"{UPLOAD_URL_PREFIX}{unique_name}"
    return jsonify({'url': public_url}), 201


# ── Article Comment Notification API ───────────────────────────────────────

@app.route('/api/article-notifications')
def get_article_notifications():
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Login required'}), 401
    notifs = (ArticleCommentNotification.query
              .filter_by(recipient_username=current_user.username)
              .order_by(ArticleCommentNotification.created_at.desc())
              .limit(50).all())
    unread = (ArticleCommentNotification.query
              .filter_by(recipient_username=current_user.username, is_read=False)
              .count())

    def _ser(n):
        c = n.comment
        return {
            'id': n.id,
            'notification_type': n.notification_type,
            'is_read': n.is_read,
            'created_at': _fmt_est(n.created_at),
            'post_id': n.post_id,
            'comment_id': n.comment_id,
            'comment_parent_id': c.parent_id if c else None,
            'comment_content': (c.content[:120] if c else ''),
            'author_name': (c.author_name if c else ''),
            'post_title': (n.post.title if n.post else ''),
        }

    return jsonify({'notifications': [_ser(n) for n in notifs], 'unread_count': unread})


@app.route('/api/article-notifications/<int:notif_id>/read', methods=['POST'])
def mark_article_notification_read(notif_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Login required'}), 401
    n = ArticleCommentNotification.query.filter_by(
        id=notif_id, recipient_username=current_user.username
    ).first_or_404()
    if not n.is_read:
        n.is_read = True
        n.read_at = _datetime.utcnow()
        db.session.commit()
    return jsonify({'success': True})


@app.route('/api/article-notifications/read-all', methods=['POST'])
def mark_all_article_notifications_read():
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Login required'}), 401
    now = _datetime.utcnow()
    ArticleCommentNotification.query.filter_by(
        recipient_username=current_user.username, is_read=False
    ).update({'is_read': True, 'read_at': now})
    db.session.commit()
    return jsonify({'success': True})


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('index'))