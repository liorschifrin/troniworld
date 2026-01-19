from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import app, db
from .models import Post, User


def get_current_user() -> User | None:
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)

@app.route('/')
def index():
    current_user = get_current_user()
    posts = Post.query.all()
    return render_template('index.html', current_user=current_user, posts=posts)


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
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        is_admin = request.form.get('is_admin', '0') == '1'

        if not username or not password:
            flash('Username and password are required.')
            return redirect(url_for('register'))

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash('Username already exists.')
            return redirect(url_for('register'))

        user = User(
            username=username,
            hashed_password=generate_password_hash(password),
            is_admin=is_admin,
        )
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash('Registration successful.')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.hashed_password, password):
            flash('Invalid username or password.')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        flash('Logged in.')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/post/<int:post_id>', methods=['GET'])
def post(post_id):
    post = Post.query.get_or_404(post_id)
    current_user = get_current_user()
    return render_template('post.html', post=post, current_user=current_user)


@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
def edit_post(post_id):
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return redirect(url_for('index'))

    post = Post.query.get_or_404(post_id)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not author or not content:
            flash('Title, author, and content are required.')
            return redirect(url_for('edit_post', post_id=post_id))

        post.title = title
        post.author = author
        post.content = content
        db.session.commit()
        flash('Post updated.')
        return redirect(url_for('post', post_id=post_id))

    return render_template('edit_post.html', post=post)

@app.route('/new_post', methods=['GET', 'POST'])
def new_post():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return redirect(url_for('index'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        content = request.form.get('content', '').strip()

        if not title or not author or not content:
            flash('Title, author, and content are required.')
            return redirect(url_for('new_post'))

        post = Post(title=title, author=author, content=content)
        db.session.add(post)
        db.session.commit()
        flash('Post created.')
        return redirect(url_for('index'))

    return render_template('new_post.html', current_user=current_user)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('index'))