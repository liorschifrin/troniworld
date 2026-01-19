from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import app, db
from .models import User

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    # If an admin account already exists, redirect to login unless admin is logged in. Otherwise, allow registration.
    admin_existing = User.query.filter_by(is_admin=True).first()
    if admin_existing:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        current_user = User.query.get(user_id)
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


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    flash('Logged out.')
    return redirect(url_for('index'))