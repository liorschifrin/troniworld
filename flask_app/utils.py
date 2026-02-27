from flask import session, redirect, url_for, request, flash
from functools import wraps

from .models import User

def get_current_user() -> User | None:
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def login_required(f):
    """Decorator to require authentication for a route"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            # Use relative path so _login_template can detect /film or /admin prefix
            next_url = request.path
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login', next=next_url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require authentication AND admin status"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            next_url = request.path
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login', next=next_url))
        if not user.is_admin:
            flash('You must be an admin to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def leadership_required(f):
    """Decorator to require authentication AND (admin or leadership status)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            next_url = request.path
            flash('Please log in to access this page.', 'info')
            return redirect(url_for('login', next=next_url))
        if not (user.is_admin or user.is_leadership):
            flash('You must be an admin or leadership member to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
