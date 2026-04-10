from flask import flash, jsonify, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from sqlalchemy import func
import os

from . import app, db
from .models import Player, User
from .utils import get_current_user, admin_required


@app.route('/admin/users', methods=['GET', 'POST'], endpoint='manage_users')
@admin_required
def manage_users():
    """Admin page to manage users"""
    current_user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            username = request.form.get('username', '').strip().capitalize()
            is_admin = request.form.get('is_admin') == 'on'
            is_leadership = request.form.get('is_leadership') == 'on'
            player_name = request.form.get('player_name', '').strip()

            if not username:
                flash('Username is required.', 'error')
                return redirect(url_for('manage_users'))

            # Check if username already exists
            existing = User.query.filter(func.lower(User.username) == username.lower()).first()
            if existing:
                flash('Username already exists.', 'error')
                return redirect(url_for('manage_users'))

            # Get the appropriate shared password based on role
            if is_admin:
                password = os.getenv('FILM_ADMIN_PASSWORD')
            else:
                password = os.getenv('FILM_USER_PASSWORD')

            if not password:
                flash('Shared passwords not configured in .env file.', 'error')
                return redirect(url_for('manage_users'))

            # Get player if specified
            player = None
            if player_name:
                player = Player.query.filter_by(name=player_name).first()
                if not player:
                    flash(f'Player "{player_name}" not found.', 'error')
                    return redirect(url_for('manage_users'))

            # Create new user with shared password
            new_user = User(
                username=username,
                hashed_password=generate_password_hash(password.lower()),
                is_admin=is_admin,
                is_leadership=is_leadership,
                player_id=player.id if player else None
            )

            try:
                db.session.add(new_user)
                db.session.commit()
                flash(f'User "{username}" created successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating user: {str(e)}', 'error')

            return redirect(url_for('manage_users'))

        elif action == 'delete':
            user_id = request.form.get('user_id')
            if user_id:
                try:
                    user_id_int = int(user_id)
                except (TypeError, ValueError):
                    flash('Invalid user id.', 'error')
                    return redirect(url_for('manage_users'))
                user_to_delete = db.session.get(User, user_id_int)
                if user_to_delete:
                    if user_to_delete.id == current_user.id:
                        flash('You cannot delete your own account.', 'error')
                    else:
                        try:
                            db.session.delete(user_to_delete)
                            db.session.commit()
                            flash(f'User "{user_to_delete.username}" deleted.', 'success')
                        except Exception as e:
                            db.session.rollback()
                            flash(f'Error deleting user: {str(e)}', 'error')
            return redirect(url_for('manage_users'))

        elif action == 'toggle_role':
            user_id = request.form.get('user_id')
            role_type = request.form.get('role_type')  # 'admin' or 'leadership'

            if user_id and role_type:
                user_to_update = db.session.get(User, user_id)
                if user_to_update:
                    try:
                        if role_type == 'admin':
                            # Toggle admin status
                            user_to_update.is_admin = not user_to_update.is_admin

                            # Update password based on new role
                            if user_to_update.is_admin:
                                password = os.getenv('FILM_ADMIN_PASSWORD')
                            else:
                                password = os.getenv('FILM_USER_PASSWORD')

                            if password:
                                user_to_update.hashed_password = generate_password_hash(password.lower())

                            status = "enabled" if user_to_update.is_admin else "disabled"
                            message = f'Admin status {status} for "{user_to_update.username}". Password updated to {"admin" if user_to_update.is_admin else "user"} password.'

                        elif role_type == 'leadership':
                            # Toggle leadership status
                            user_to_update.is_leadership = not user_to_update.is_leadership
                            status = "enabled" if user_to_update.is_leadership else "disabled"
                            message = f'Leadership status {status} for "{user_to_update.username}".'

                        db.session.commit()

                        # Return JSON for AJAX requests
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify({
                                'success': True,
                                'message': message,
                                'user_id': user_id,
                                'role_type': role_type,
                                'new_value': user_to_update.is_admin if role_type == 'admin' else user_to_update.is_leadership
                            })
                        else:
                            flash(message, 'success')
                    except Exception as e:
                        db.session.rollback()
                        error_msg = f'Error updating user: {str(e)}'
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                            return jsonify({'success': False, 'message': error_msg}), 500
                        else:
                            flash(error_msg, 'error')
            return redirect(url_for('manage_users'))

    # GET request - show user management page
    all_users = User.query.order_by(User.username).all()
    all_players = Player.query.order_by(Player.name).all()

    return render_template('film_room/forms/manage_users.html',
                         current_user=current_user,
                         all_users=all_users,
                         all_players=all_players)


@app.route('/admin/users/create_all_players', methods=['POST'], endpoint='create_users_for_all_players')
@admin_required
def create_users_for_all_players():
    """Bulk create users for all players that don't have users yet"""
    current_user = get_current_user()

    # Use shared user password from environment
    password = os.getenv('FILM_USER_PASSWORD')
    if not password:
        flash('FILM_USER_PASSWORD not configured in .env file.', 'error')
        return redirect(url_for('manage_users'))

    players_without_users = Player.query.filter(~Player.id.in_(
        db.session.query(User.player_id).filter(User.player_id.isnot(None))
    )).all()

    created_count = 0
    skipped_count = 0

    for player in players_without_users:
        # Check if username already exists
        if User.query.filter(func.lower(User.username) == player.name.lower()).first():
            skipped_count += 1
            continue

        new_user = User(
            username=player.name.capitalize(),
            hashed_password=generate_password_hash(password.lower()),
            is_admin=False,
            is_leadership=False,
            player_id=player.id
        )
        db.session.add(new_user)
        created_count += 1

    try:
        db.session.commit()
        flash(f'Created {created_count} users for players with shared password. ({skipped_count} skipped due to existing usernames)', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating users: {str(e)}', 'error')

    return redirect(url_for('manage_users'))
