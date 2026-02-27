from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func
import csv
import io
import os

_EST = ZoneInfo('America/New_York')

def fmt_dt_est(dt):
    """Format a naive-UTC datetime as a human-readable EST/EDT string."""
    if dt is None:
        return ''
    aware = dt.replace(tzinfo=timezone.utc).astimezone(_EST)
    return aware.strftime('%b %d, %Y %I:%M %p')

from . import app, db
from .models import Player, Game, Point, Event, Comment, point_players, User, VideoWatchSession, LoginEvent
from .utils import get_current_user, login_required, admin_required


# =========================
# HELPER FUNCTIONS
# =========================

def link_or_create_user_for_player(player):
    """
    When a new player is created, check if a user with the same username exists.
    If so, link them. If not, auto-create a user for them.
    
    Args:
        player: The Player object that was just created
    """
    # Check if a user with this username already exists
    existing_user = User.query.filter(func.lower(User.username) == player.name.lower()).first()
    
    if existing_user:
        # Link the existing user to this player (if not already linked)
        if not existing_user.player_id:
            existing_user.player_id = player.id
            db.session.flush()
    else:
        # Auto-create a new user for this player
        password = os.getenv('FILM_USER_PASSWORD')
        if password:
            new_user = User(
                username=player.name.capitalize(),
                hashed_password=generate_password_hash(password.lower()),
                is_admin=False,
                is_leadership=False,
                player_id=player.id
            )
            db.session.add(new_user)
            db.session.flush()


# =========================
# USER MANAGEMENT (Admin Only)
# =========================

@app.route('/admin/users', methods=['GET', 'POST'])
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
                user_to_delete = User.query.get(user_id)
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
                user_to_update = User.query.get(user_id)
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
    
    return render_template('manage_users.html', 
                         current_user=current_user, 
                         all_users=all_users,
                         all_players=all_players)


@app.route('/admin/users/create_all_players', methods=['POST'])
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


# =========================
# FILM ROUTES
# =========================

@app.route('/film/my-games')
@login_required
def my_games():
    current_user = get_current_user()
    
    # Get games where the user's linked player participated
    my_games_list = []
    games_with_stats = []
    total_o_points = 0
    total_o_scored = 0
    total_d_points = 0
    total_d_scored = 0
    
    if current_user.player:
        # Get all games this player was in (through game_roster)
        my_games_list = current_user.player.games
        # Sort by date descending (game_date is a string in ISO format YYYY-MM-DD, or None)
        my_games_list = sorted(my_games_list, key=lambda g: (g.game_date or '', g.id), reverse=True)
        
        # Calculate stats for each game
        for game in my_games_list:
            # Get points where this player participated
            player_points = [p for p in game.points if current_user.player in p.players]
            
            # Calculate O and D stats
            o_points = [p for p in player_points if p.tron_o]
            d_points = [p for p in player_points if not p.tron_o]
            
            o_count = len(o_points)
            o_scored = len([p for p in o_points if p.tron_point])
            hold_pct = (o_scored / o_count * 100) if o_count > 0 else 0
            
            d_count = len(d_points)
            d_scored = len([p for p in d_points if p.tron_point])
            break_pct = (d_scored / d_count * 100) if d_count > 0 else 0
            
            games_with_stats.append({
                'game': game,
                'o_count': o_count,
                'o_scored': o_scored,
                'hold_pct': hold_pct,
                'd_count': d_count,
                'd_scored': d_scored,
                'break_pct': break_pct
            })
            
            # Add to totals
            total_o_points += o_count
            total_o_scored += o_scored
            total_d_points += d_count
            total_d_scored += d_scored
    
    # Calculate total percentages
    total_hold_pct = (total_o_scored / total_o_points * 100) if total_o_points > 0 else 0
    total_break_pct = (total_d_scored / total_d_points * 100) if total_d_points > 0 else 0
    
    return render_template('my_games.html', 
                         current_user=current_user, 
                         games_with_stats=games_with_stats,
                         total_o_points=total_o_points,
                         total_o_scored=total_o_scored,
                         total_hold_pct=total_hold_pct,
                         total_d_points=total_d_points,
                         total_d_scored=total_d_scored,
                         total_break_pct=total_break_pct)


@app.route('/film/data')
@login_required
def tron_data():
    """Team-wide game data and statistics page."""
    current_user = get_current_user()

    games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()

    # ── Per-game stats ──────────────────────────────────────────────
    games_with_stats = []
    total_o_points = total_o_scored = 0
    total_d_points = total_d_scored = 0
    wins = losses = ties = 0

    for game in games:
        pts = list(game.points)

        o_pts   = [p for p in pts if p.tron_o]
        d_pts   = [p for p in pts if not p.tron_o]

        o_count   = len(o_pts)
        o_scored  = len([p for p in o_pts if p.tron_point])
        d_count   = len(d_pts)
        d_scored  = len([p for p in d_pts if p.tron_point])
        hold_pct  = (o_scored / o_count * 100) if o_count > 0 else None
        break_pct = (d_scored / d_count * 100) if d_count > 0 else None

        total_o_points += o_count;  total_o_scored += o_scored
        total_d_points += d_count;  total_d_scored += d_scored

        if game.final_score_tron is not None and game.final_score_opponent is not None:
            if game.final_score_tron > game.final_score_opponent:
                wins += 1
            elif game.final_score_tron < game.final_score_opponent:
                losses += 1
            else:
                ties += 1

        games_with_stats.append({
            'game': game,
            'o_count': o_count, 'o_scored': o_scored, 'hold_pct': hold_pct,
            'd_count': d_count, 'd_scored': d_scored, 'break_pct': break_pct,
        })

    total_hold_pct  = (total_o_scored / total_o_points * 100) if total_o_points > 0 else None
    total_break_pct = (total_d_scored / total_d_points * 100) if total_d_points > 0 else None

    # ── Player leaderboard ──────────────────────────────────────────
    players = Player.query.filter_by(active=True).order_by(Player.name).all()
    player_stats = []
    for player in players:
        all_pts   = list(player.points)
        if not all_pts:
            continue
        o_pts     = [p for p in all_pts if p.tron_o]
        d_pts     = [p for p in all_pts if not p.tron_o]
        o_count   = len(o_pts)
        o_scored  = len([p for p in o_pts if p.tron_point])
        d_count   = len(d_pts)
        d_scored  = len([p for p in d_pts if p.tron_point])
        player_stats.append({
            'player': player,
            'total_pts': len(all_pts),
            'games_played': len(player.games),
            'o_count': o_count, 'o_scored': o_scored,
            'hold_pct': (o_scored / o_count * 100) if o_count > 0 else None,
            'd_count': d_count, 'd_scored': d_scored,
            'break_pct': (d_scored / d_count * 100) if d_count > 0 else None,
        })
    # Sort by total points played descending
    player_stats.sort(key=lambda x: x['total_pts'], reverse=True)

    # ── Tendency breakdowns (all games combined) ────────────────────
    all_pts = Point.query.all()

    pull_play_counts = {}
    for p in all_pts:
        if not p.tron_o and p.pull_play:
            pull_play_counts[p.pull_play] = pull_play_counts.get(p.pull_play, 0) + 1

    defense_counts = {}
    defense_scored = {}
    for p in all_pts:
        if not p.tron_o and p.defense_type:
            defense_counts[p.defense_type] = defense_counts.get(p.defense_type, 0) + 1
            if p.tron_point:
                defense_scored[p.defense_type] = defense_scored.get(p.defense_type, 0) + 1

    offense_faced_counts = {}
    offense_faced_scored = {}
    for p in all_pts:
        if not p.tron_o and p.offense_faced:
            offense_faced_counts[p.offense_faced] = offense_faced_counts.get(p.offense_faced, 0) + 1
            if p.tron_point:
                offense_faced_scored[p.offense_faced] = offense_faced_scored.get(p.offense_faced, 0) + 1

    defense_breakdown = [
        {
            'name': name,
            'count': count,
            'scored': defense_scored.get(name, 0),
            'break_pct': (defense_scored.get(name, 0) / count * 100) if count > 0 else None,
        }
        for name, count in sorted(defense_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    offense_faced_breakdown = [
        {
            'name': name,
            'count': count,
            'scored': offense_faced_scored.get(name, 0),
            'break_pct': (offense_faced_scored.get(name, 0) / count * 100) if count > 0 else None,
        }
        for name, count in sorted(offense_faced_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    pull_breakdown = [
        {'name': name, 'count': count}
        for name, count in sorted(pull_play_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return render_template(
        'tron_data.html',
        current_user=current_user,
        games_with_stats=games_with_stats,
        total_games=len(games),
        wins=wins, losses=losses, ties=ties,
        total_o_points=total_o_points, total_o_scored=total_o_scored,
        total_hold_pct=total_hold_pct,
        total_d_points=total_d_points, total_d_scored=total_d_scored,
        total_break_pct=total_break_pct,
        player_stats=player_stats,
        defense_breakdown=defense_breakdown,
        offense_faced_breakdown=offense_faced_breakdown,
        pull_breakdown=pull_breakdown,
    )


@app.route('/film/games')
@login_required
def games_list():
    current_user = get_current_user()
    games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()
    return render_template('games_list.html', current_user=current_user, games=games)


@app.route('/film/games/<int:game_id>')
@login_required
def view_game(game_id):
    current_user = get_current_user()
    game = Game.query.get_or_404(game_id)
    
    # Get all unique point detail field values across ALL games
    all_pull_plays = set()
    all_defense_types = set()
    all_offense_faced = set()
    
    all_points = Point.query.all()
    for point in all_points:
        if point.pull_play:
            all_pull_plays.add(point.pull_play)
        if point.defense_type:
            all_defense_types.add(point.defense_type)
        if point.offense_faced:
            all_offense_faced.add(point.offense_faced)
    
    point_field_options = {
        'pull_play': sorted(list(all_pull_plays)),
        'defense_type': sorted(list(all_defense_types)),
        'offense_faced': sorted(list(all_offense_faced))
    }
    
    # Prepare player sheet data if points exist
    player_sheet_data = None
    points = game.points.order_by(Point.point_index).all()
    
    if points:
        # Get all players in order from player_order_data if available
        all_players = []
        separator_index = None
        
        if game.player_order_data and 'players' in game.player_order_data:
            # Use the stored player order
            all_players = game.player_order_data['players']
            separator_index = game.player_order_data.get('separator_index')
        elif game.roster:
            # Fallback to roster order
            all_players = [p.name for p in game.roster]
        else:
            # Fallback: collect players from points
            player_set = set()
            for point in points:
                for player in point.players:
                    if player.name not in player_set:
                        all_players.append(player.name)
                        player_set.add(player.name)
        
        # Build player sheet structure
        player_sheet_data = {
            'points': points,
            'players': all_players,
            'separator_index': separator_index,
            'point_players': {}  # Map of point_index -> [player_names]
        }
        
        for point in points:
            player_sheet_data['point_players'][point.point_index] = [p.name for p in point.players]
    
    users = [u.username for u in User.query.order_by(User.username).all()]
    return render_template('game_player.html', current_user=current_user, game=game, player_sheet_data=player_sheet_data, point_field_options=point_field_options, users=users)


@app.route('/film/games/new', methods=['GET', 'POST'])
@admin_required
def new_game():
    current_user = get_current_user()
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        opponent = request.form.get('opponent', '').strip()
        youtube_id = request.form.get('youtube_id', '').strip()
        game_date = request.form.get('game_date', '').strip()
        final_score_tron = request.form.get('final_score_tron', '').strip()
        final_score_opponent = request.form.get('final_score_opponent', '').strip()
        
        # Validate required fields
        if not title or not opponent:
            flash('Title and opponent are required.', 'error')
            return render_template('new_game.html', current_user=current_user)
        
        # Convert scores to integers if provided
        tron_score = int(final_score_tron) if final_score_tron else None
        opp_score = int(final_score_opponent) if final_score_opponent else None
        
        # Create new game
        new_game = Game(
            title=title,
            opponent=opponent,
            youtube_id=youtube_id if youtube_id else None,
            game_date=game_date if game_date else None,
            final_score_tron=tron_score,
            final_score_opponent=opp_score
        )
        
        try:
            db.session.add(new_game)
            db.session.commit()
            flash(f'Game "{title}" created successfully!', 'success')
            return redirect(url_for('player'))  # Redirect to player page for now
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating game: {str(e)}', 'error')
            return render_template('new_game.html', current_user=current_user)
    
    # GET request - show the form
    return render_template('new_game.html', current_user=current_user)


@app.route('/film/games/<int:game_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_game(game_id):
    current_user = get_current_user()
    
    game = Game.query.get_or_404(game_id)
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        opponent = request.form.get('opponent', '').strip()
        youtube_id = request.form.get('youtube_id', '').strip()
        game_date = request.form.get('game_date', '').strip()
        final_score_tron = request.form.get('final_score_tron', '').strip()
        final_score_opponent = request.form.get('final_score_opponent', '').strip()
        
        # Validate required fields
        if not title or not opponent:
            flash('Title and opponent are required.', 'error')
            return render_template('edit_game.html', current_user=current_user, game=game)
        
        # Convert scores to integers if provided
        tron_score = int(final_score_tron) if final_score_tron else None
        opp_score = int(final_score_opponent) if final_score_opponent else None
        
        # Update game fields
        game.title = title
        game.opponent = opponent
        game.youtube_id = youtube_id if youtube_id else None
        game.game_date = game_date if game_date else None
        game.final_score_tron = tron_score
        game.final_score_opponent = opp_score
        
        try:
            db.session.commit()
            flash(f'Game "{title}" updated successfully!', 'success')
            return redirect(url_for('view_game', game_id=game.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating game: {str(e)}', 'error')
            return render_template('edit_game.html', current_user=current_user, game=game)
    
    # GET request - show the form
    return render_template('edit_game.html', current_user=current_user, game=game)


# =========================
# COMMENTS API
# =========================

@app.route('/film/api/games/<int:game_id>/comments', methods=['GET'])
@login_required
def get_comments(game_id):
    """Get all comments for a game"""
    game = Game.query.get_or_404(game_id)
    # Sort by timestamp (nulls last), then by created_at for comments without timestamps
    comments = Comment.query.filter_by(game_id=game_id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc()
    ).all()
    
    comments_list = []
    for comment in comments:
        comment_data = {
            'id': comment.id,
            'author_name': comment.author_name,
            'content': comment.content,
            'comment_type': comment.comment_type,
            'timestamp': comment.timestamp,
            'created_at': fmt_dt_est(comment.created_at),
            'replies': []
        }
        
        # Get replies (1-level nesting)
        replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at.asc()).all()
        for reply in replies:
            comment_data['replies'].append({
                'id': reply.id,
                'author_name': reply.author_name,
                'content': reply.content,
                'created_at': fmt_dt_est(reply.created_at)
            })
        
        comments_list.append(comment_data)
    
    return jsonify({'comments': comments_list})


@app.route('/film/api/games/<int:game_id>/comments', methods=['POST'])
@login_required
def create_comment(game_id):
    """Create a new comment for a game"""
    game = Game.query.get_or_404(game_id)
    
    # Get the current user
    current_user = get_current_user()
    
    data = request.get_json()
    content = data.get('content', '').strip()
    # Use the logged-in user's username, or fallback to Anonymous if not logged in
    author_name = current_user.username if current_user else 'Anonymous'
    comment_type = data.get('comment_type', 'Comment')
    parent_id = data.get('parent_id')
    timestamp = data.get('timestamp')
    point_id = data.get('point_id')
    
    # Content is required for non-Event types
    if not content and comment_type != 'Event':
        return jsonify({'error': 'Content is required'}), 400
    
    # Validate comment_type
    valid_types = ['Comment', 'Question', 'Highlight', 'Event']
    if comment_type not in valid_types:
        comment_type = 'Comment'
    
    new_comment = Comment(
        game_id=game_id,
        point_id=point_id,
        parent_id=parent_id,
        comment_type=comment_type,
        author_name=author_name,
        timestamp=timestamp,
        content=content
    )
    
    try:
        db.session.add(new_comment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'author_name': new_comment.author_name,
                'content': new_comment.content,
                'comment_type': new_comment.comment_type,
                'timestamp': new_comment.timestamp,
                'created_at': fmt_dt_est(new_comment.created_at),
                'parent_id': new_comment.parent_id
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/film/api/games/<int:game_id>/comments/<int:comment_id>', methods=['DELETE'])
@login_required
def delete_comment(game_id, comment_id):
    """Delete a comment - users can delete their own comments, admins can delete any"""
    current_user = get_current_user()
    
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    
    # Check if user is authorized to delete this comment
    if not current_user.is_admin and comment.author_name != current_user.username:
        return jsonify({'error': 'Unauthorized - you can only delete your own comments'}), 403
    
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/film/api/games/<int:game_id>/comments/<int:comment_id>', methods=['PATCH'])
@login_required
def update_comment(game_id, comment_id):
    """Update a comment - users can only edit their own comments"""
    current_user = get_current_user()
    
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    
    # Check if user is authorized to edit this comment (only own comments)
    if comment.author_name != current_user.username:
        return jsonify({'error': 'Unauthorized - you can only edit your own comments'}), 403
    
    data = request.get_json()
    new_content = data.get('content', '').strip()
    new_comment_type = data.get('comment_type')
    
    # Content is required for non-Event types
    if not new_content and (not new_comment_type or new_comment_type != 'Event'):
        return jsonify({'error': 'Content is required'}), 400
    
    # Validate comment_type if provided
    valid_types = ['Comment', 'Question', 'Highlight', 'Event']
    if new_comment_type and new_comment_type not in valid_types:
        return jsonify({'error': 'Invalid comment type'}), 400
    
    try:
        comment.content = new_content
        if new_comment_type:
            comment.comment_type = new_comment_type
        db.session.commit()
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'author_name': comment.author_name,
                'comment_type': comment.comment_type,
                'timestamp': comment.timestamp,
                'created_at': fmt_dt_est(comment.created_at),
                'parent_id': comment.parent_id
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# =========================
# CSV UPLOAD FOR GAME DATA
# =========================

@app.route('/film/games/<int:game_id>/upload_csv', methods=['GET', 'POST'])
@admin_required
def upload_game_csv(game_id):
    """Upload CSV to populate game points and player data"""
    current_user = get_current_user()
    
    game = Game.query.get_or_404(game_id)
    
    if request.method == 'POST':
        # Check if file was uploaded
        if 'csv_file' not in request.files:
            flash('No file uploaded.', 'error')
            return render_template('upload_game_csv.html', current_user=current_user, game=game)
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return render_template('upload_game_csv.html', current_user=current_user, game=game)
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'error')
            return render_template('upload_game_csv.html', current_user=current_user, game=game)
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            rows = list(csv_reader)
            
            if len(rows) < 4:
                flash('CSV file must have at least 4 rows (O/D row, TRON row, Enemy row, and player rows).', 'error')
                return render_template('upload_game_csv.html', current_user=current_user, game=game)
            
            # Parse CSV structure
            od_row = rows[0]  # O/D indicator row
            tron_row = rows[1]  # TRON scores row
            enemy_row = rows[2]  # Enemy scores row
            # Skip empty row if exists
            player_start_idx = 3
            if player_start_idx < len(rows) and all(cell.strip() == '' for cell in rows[player_start_idx]):
                player_start_idx = 4
            
            # Get player rows, stopping at "END PLAYERS" marker
            # Also track player order and section separator
            player_rows = []
            player_names_ordered = []
            separator_index = None
            
            for idx, row in enumerate(rows[player_start_idx:]):
                if row and row[0].strip().upper() == 'END PLAYERS':
                    break
                
                # Check if this is an empty row (potential separator)
                if all(cell.strip() == '' for cell in row):
                    if player_names_ordered and separator_index is None:
                        # This is the first empty row after players started
                        separator_index = len(player_names_ordered)
                    continue
                
                # Valid player row
                player_name = row[0].strip() if row else ''
                if player_name:
                    player_rows.append(row)
                    player_names_ordered.append(player_name)
            
            # Find the number of point columns (starting from column 1, index 1)
            num_points = len(od_row) - 1  # Subtract first column (label)
            
            # Clear existing roster and points for this game
            game.roster.clear()
            # Delete points using synchronize_session=False to avoid autoflush issues
            Point.query.filter_by(game_id=game_id).delete(synchronize_session=False)
            # Commit the deletion before creating new points
            db.session.commit()
            # Clear the session to remove any cached objects
            db.session.expire_all()
            
            # Re-fetch the game object to ensure fresh state
            game = Game.query.get(game_id)
            
            # Track all players in this game for roster
            roster_players = set()
            
            # Create points
            for point_idx in range(1, num_points + 1):
                col_idx = point_idx  # CSV column index (0-indexed, but first col is labels)
                
                if col_idx >= len(od_row):
                    continue
                
                # Determine tron_o (O = True, X = False)
                od_val = od_row[col_idx].strip().upper()
                if od_val not in ['O', 'X']:
                    continue  # Skip invalid columns
                tron_o = (od_val == 'O')
                
                # Determine tron_point (value in TRON row = True, value in Enemy row = False)
                tron_score = tron_row[col_idx].strip() if col_idx < len(tron_row) else ''
                enemy_score = enemy_row[col_idx].strip() if col_idx < len(enemy_row) else ''
                
                if tron_score:
                    tron_point = True
                elif enemy_score:
                    tron_point = False
                else:
                    continue  # Skip if neither team scored
                
                # Create point
                point = Point(
                    game_id=game_id,
                    point_index=point_idx,
                    tron_o=tron_o,
                    tron_point=tron_point
                )
                db.session.add(point)
                db.session.flush()  # Flush to get point.id
                
                # Track players added to this point to avoid duplicates
                added_players = set()
                
                # Add players to point
                for player_row in player_rows:
                    if not player_row:
                        continue
                    
                    player_name = player_row[0].strip()
                    if not player_name:
                        continue
                    
                    # Check if player participated in this point
                    if col_idx < len(player_row) and player_row[col_idx].strip():
                        # Skip if we've already added this player to this point
                        if player_name in added_players:
                            continue
                        
                        # Get or create player
                        player = Player.query.filter_by(name=player_name).first()
                        if not player:
                            player = Player(name=player_name, active=True)
                            db.session.add(player)
                            db.session.flush()
                            # Auto-create or link user for new player
                            link_or_create_user_for_player(player)
                        
                        # Add player to point
                        point.players.append(player)
                        added_players.add(player_name)
                        roster_players.add(player)
            
            # Update game roster (already cleared at the start)
            for player in roster_players:
                game.roster.append(player)
            
            # Store player order data
            game.player_order_data = {
                'players': player_names_ordered,
                'separator_index': separator_index
            }
            
            db.session.commit()
            flash(f'Successfully uploaded game data! Created {num_points} points with player assignments.', 'success')
            return redirect(url_for('view_game', game_id=game.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing CSV: {str(e)}', 'error')
            return render_template('upload_game_csv.html', current_user=current_user, game=game)
    
    # GET request - show upload form
    return render_template('upload_game_csv.html', current_user=current_user, game=game)


@app.route('/film/games/<int:game_id>/delete_player_sheet', methods=['POST'])
@admin_required
def delete_player_sheet(game_id):
    """Delete all points and player associations for a game"""
    current_user = get_current_user()
    
    game = Game.query.get_or_404(game_id)
    
    try:
        # Clear game roster
        game.roster.clear()
        
        # Delete all points (this will cascade delete point_players associations)
        Point.query.filter_by(game_id=game_id).delete()
        
        db.session.commit()
        flash('Player sheet data deleted successfully. You can now upload a new CSV.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting player sheet: {str(e)}', 'error')
    
    return redirect(url_for('view_game', game_id=game.id))


@app.route('/film/api/games/<int:game_id>/points/<int:point_id>', methods=['PATCH'])
@admin_required
def update_point(game_id, point_id):
    """Update point information (pull_play, defense_type, offense_faced, timestamp_start)"""
    current_user = get_current_user()
    
    point = Point.query.filter_by(id=point_id, game_id=game_id).first_or_404()
    
    try:
        data = request.get_json()
        
        # Update allowed fields
        if 'pull_play' in data:
            point.pull_play = data['pull_play']
        if 'defense_type' in data:
            point.defense_type = data['defense_type']
        if 'offense_faced' in data:
            point.offense_faced = data['offense_faced']
        if 'timestamp_start' in data:
            point.timestamp_start = data['timestamp_start']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Point updated successfully'})
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# =========================
# ANALYTICS TRACKING API
# =========================

@app.route('/film/api/games/<int:game_id>/track-watch-time', methods=['POST'])
@login_required
def track_watch_time(game_id):
    """Track how much time a user has spent watching a game video"""
    current_user = get_current_user()
    
    # Verify game exists
    game = Game.query.get_or_404(game_id)
    
    try:
        data = request.get_json()
        seconds_watched = data.get('seconds_watched', 0)
        
        if seconds_watched <= 0:
            return jsonify({'success': False, 'error': 'Invalid watch duration'}), 400
        
        # Find or create a watch session for this user and game
        # We'll create a new session for each page load/visit
        session_id = data.get('session_id')
        
        if session_id:
            # Try to find existing session
            watch_session = VideoWatchSession.query.filter_by(
                id=session_id,
                user_id=current_user.id,
                game_id=game_id
            ).first()
        else:
            watch_session = None
        
        if not watch_session:
            # Create new watch session
            watch_session = VideoWatchSession(
                user_id=current_user.id,
                game_id=game_id,
                watch_duration_seconds=seconds_watched
            )
            db.session.add(watch_session)
        else:
            # Update existing session
            watch_session.watch_duration_seconds += seconds_watched
            watch_session.last_updated = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session_id': watch_session.id,
            'total_watched': watch_session.watch_duration_seconds
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/film/analytics')
@admin_required
def analytics_dashboard():
    """Admin analytics dashboard showing user engagement metrics"""
    current_user = get_current_user()
    
    # Get all users
    users = User.query.all()
    
    # Build analytics data for each user
    user_analytics = []
    
    for user in users:
        # Count logins
        login_count = LoginEvent.query.filter_by(user_id=user.id).count()
        
        # Get total watch time across all games
        total_watch_time_result = db.session.query(
            func.sum(VideoWatchSession.watch_duration_seconds)
        ).filter_by(user_id=user.id).scalar()
        total_watch_minutes = (total_watch_time_result or 0) / 60.0
        
        # Get watch time per game
        game_watch_times = db.session.query(
            Game.id,
            Game.title,
            Game.opponent,
            func.sum(VideoWatchSession.watch_duration_seconds).label('total_seconds')
        ).join(
            VideoWatchSession, VideoWatchSession.game_id == Game.id
        ).filter(
            VideoWatchSession.user_id == user.id
        ).group_by(
            Game.id, Game.title, Game.opponent
        ).all()
        
        game_breakdown = []
        for game_id, title, opponent, total_seconds in game_watch_times:
            game_breakdown.append({
                'game_id': game_id,
                'title': title,
                'opponent': opponent,
                'minutes_watched': (total_seconds or 0) / 60.0
            })
        
        # Sort game breakdown by minutes watched (descending)
        game_breakdown.sort(key=lambda x: x['minutes_watched'], reverse=True)
        
        # Count comments made by this user
        # Comments store author_name, so we match by username
        comment_count = Comment.query.filter_by(author_name=user.username).count()
        
        user_analytics.append({
            'user': user,
            'login_count': login_count,
            'total_watch_minutes': round(total_watch_minutes, 1),
            'game_breakdown': game_breakdown,
            'comment_count': comment_count
        })
    
    # Sort by total watch minutes (most engaged users first)
    user_analytics.sort(key=lambda x: x['total_watch_minutes'], reverse=True)
    
    # Calculate totals
    total_unique_users = len([u for u in user_analytics if u['login_count'] > 0])
    total_watch_minutes = sum([u['total_watch_minutes'] for u in user_analytics])
    total_comments = sum([u['comment_count'] for u in user_analytics])
    
    return render_template('analytics_dashboard.html', 
                          current_user=current_user,
                          user_analytics=user_analytics,
                          total_unique_users=total_unique_users,
                          total_watch_minutes=round(total_watch_minutes, 1),
                          total_comments=total_comments)