from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
import os
import uuid

from . import app, db
from .models import Post, User, LoginEvent

from .utils import get_current_user

def is_allowed_image(filename: str) -> bool:
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_IMAGE_EXTENSIONS']

@app.route('/')
def index():
    current_user = get_current_user()
    posts = Post.query.order_by(Post.created_at.desc()).all()
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
        session['user_id'] = user.id
        flash('Registration successful.')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        print("Login attempt with data:", request.form)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip().lower()

        user = User.query.filter(func.lower(User.username) == username.lower()).first()
        if not user:
            print("Login failed - user not found:", username)
            flash('Invalid username or password.')
            return redirect(url_for('login'))
        
        # Check password against shared passwords based on role
        if user.is_admin:
            expected_password = os.getenv('FILM_ADMIN_PASSWORD')
        else:
            expected_password = os.getenv('FILM_USER_PASSWORD')
        
        if not expected_password:
            print("Shared passwords not configured in environment variables.")
            flash('Authentication system not configured properly.')
            return redirect(url_for('login'))
        
        # Verify against hashed password (which was created from shared password)
        if not check_password_hash(user.hashed_password, password):
            print("Invalid username or password attempt for user:", username)
            flash('Invalid username or password.')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        
        # Track login event
        login_event = LoginEvent(user_id=user.id)
        db.session.add(login_event)
        db.session.commit()
        
        flash('Logged in.')
        
        # Redirect to original page or default to index
        next_url = request.args.get('next') or url_for('games_list')
        return redirect(next_url)

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
        created_at_str = request.form.get('created_at', '').strip()

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
        return redirect(url_for('post', post_id=post_id))

    return render_template('edit_post.html', post=post)

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

@app.route('/new_post', methods=['GET', 'POST'])
def new_post():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        print("not admin")
        return redirect(url_for('index'))

    print("admin")

    print(request.method)
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        author = request.form.get('author', '').strip()
        content = request.form.get('content', '').strip()

        print(title, author, content)

        if not title or not author or not content:
            flash('Title, author, and content are required.')
            return redirect(url_for('new_post'))

        post = Post(title=title, author=author, content=content)
        db.session.add(post)
        db.session.commit()
        flash('Post created.')
        return redirect(url_for('index'))

    return render_template('new_post.html', current_user=current_user)


@app.route('/upload_image', methods=['POST'])
def upload_image():
    current_user = get_current_user()
    if not current_user or not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    if 'upload' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    image = request.files['upload']
    if image.filename == '' or not is_allowed_image(image.filename):
        return jsonify({'error': 'Invalid image type'}), 400

    original_name = secure_filename(image.filename)
    unique_name = f"{uuid.uuid4().hex}_{original_name}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
    image.save(save_path)

    public_url = f"/static/uploads/{unique_name}"
    return jsonify({'url': public_url}), 201


@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('index'))