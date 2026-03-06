from flask import flash, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import csv
import io
import json
import os
import re

_EST = ZoneInfo('America/New_York')

def fmt_dt_est(dt):
    """Format a naive-UTC datetime as a human-readable EST/EDT string."""
    if dt is None:
        return ''
    aware = dt.replace(tzinfo=timezone.utc).astimezone(_EST)
    return aware.strftime('%b %d, %Y %I:%M %p')

from . import app, db
from .models import Player, Game, Point, Event, Comment, Tournament, point_players, User, VideoWatchSession, LoginEvent, CommentNotification
from .utils import get_current_user, login_required, admin_required


# =========================
# HELPER FUNCTIONS
# =========================

def _create_notifications_for_comment(comment, game_id, author_username, author_is_leadership):
    """Compute and persist CommentNotification rows for a comment.

    Priority order (highest wins per recipient):
      private > everyone > mention > reply > thread

    Reply notifications (only for comments with a parent_id):
      - parent comment author  → 'reply'   (someone replied to your comment)
      - other participants in the thread → 'thread' (someone replied in a thread you're in)

    Mention / private rules (applied on top, can upgrade a reply/thread to mention/private):
      - Private comment: notify only the explicit private_to recipients ('private').
      - Public comment: notify every @[username] mentioned in the content.
        @[Everyone] (leadership only) notifies all film users except the author.

    Author is never notified for their own comment.
    """

    print("Debug: Creating notification for comment with text:", comment.content)

    PRIORITY = {'private': 5, 'everyone': 4, 'mention': 3, 'reply': 2, 'thread': 1}
    notif_map = {}  # username -> notification_type

    def _set(uname, ntype):
        if not uname or uname == author_username:
            return
        existing = notif_map.get(uname)
        if existing is None or PRIORITY.get(ntype, 0) > PRIORITY.get(existing, 0):
            notif_map[uname] = ntype

    # ── Reply-thread notifications ────────────────────────────────────────
    if comment.parent_id is not None:
        parent = Comment.query.get(comment.parent_id)
        if parent:
            _set(parent.author_name, 'reply')
            # Everyone else who already replied in this thread
            siblings = Comment.query.filter(
                Comment.parent_id == comment.parent_id,
                Comment.id != comment.id,
            ).all()
            for sib in siblings:
                _set(sib.author_name, 'thread')

    # ── Mention / private notifications (can override reply/thread) ────────
    is_private = bool(comment.private_to)

    if is_private:
        try:
            private_list = json.loads(comment.private_to)
        except (ValueError, TypeError):
            private_list = []
        for uname in private_list:
            if uname and User.query.filter_by(username=uname).first():
                _set(uname, 'private')
    else:
        mention_names = re.findall(r'@\[([^\]]+)\]', comment.content)
        print("Debug: Found mention names in comment:", mention_names)
        for uname in mention_names:
            if uname == 'Everyone' and author_is_leadership:
                print("Debug: Author is leadership and mentioned @Everyone, adding notifications for all film users except the author.")
                for u in User.query.all():
                    _set(u.username, 'everyone')
            else:
                if User.query.filter_by(username=uname).first():
                    _set(uname, 'mention')

    for uname, ntype in notif_map.items():
        notif = CommentNotification(
            recipient_username=uname,
            comment_id=comment.id,
            game_id=game_id,
            notification_type=ntype,
            is_read=False,
        )
        db.session.add(notif)


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
    
    return render_template('film_room/forms/manage_users.html', 
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

    # Fetch all comments by this user for the "My Comments" section
    my_comments_rows = (
        db.session.query(
            Comment.id,
            Comment.content,
            Comment.timestamp,
            Comment.created_at,
            Comment.game_id,
            Comment.parent_id,
            Comment.private_to,
            Game.title.label('game_title'),
            Game.opponent.label('game_opponent'),
        )
        .join(Game, Comment.game_id == Game.id)
        .filter(Comment.author_name == current_user.username)
        .order_by(Comment.created_at.desc())
        .all()
    )
    my_comments = [
        {
            'id': r.id,
            'content': r.content,
            'timestamp': r.timestamp,
            'timestamp_str': (f'{r.timestamp // 60}:{r.timestamp % 60:02d}'
                              if r.timestamp is not None else None),
            'created_at': fmt_dt_est(r.created_at),
            'created_at_iso': r.created_at.isoformat() + 'Z' if r.created_at else '',
            'game_id': r.game_id,
            'is_reply': r.parent_id is not None,
            'game_title': r.game_title,
            'game_opponent': r.game_opponent,
            'private_to': (json.loads(r.private_to) if r.private_to else None),
        }
        for r in my_comments_rows
    ]

    return render_template('film_room/pages/my_games.html',
                         current_user=current_user,
                         games_with_stats=games_with_stats,
                         total_o_points=total_o_points,
                         total_o_scored=total_o_scored,
                         total_hold_pct=total_hold_pct,
                         total_d_points=total_d_points,
                         total_d_scored=total_d_scored,
                         total_break_pct=total_break_pct,
                         my_comments=my_comments)


@app.route('/film/data')
@login_required
def tron_data():
    """Team-wide game data and statistics page."""
    current_user = get_current_user()

    all_games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()
    all_tournaments = Tournament.query.order_by(Tournament.start_date.desc().nullslast(), Tournament.name).all()

    # ── Filter by selected game IDs (default = all) ─────────────────
    selected_ids = request.args.getlist('game_ids', type=int)
    if selected_ids:
        selected_id_set = set(selected_ids)
        games = [g for g in all_games if g.id in selected_id_set]
    else:
        selected_id_set = {g.id for g in all_games}
        games = all_games

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
        all_pts   = [p for p in player.points if p.game_id in selected_id_set]
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
    all_pts = [p for p in Point.query.all() if p.game_id in selected_id_set]

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
        'film_room/pages/tron_data.html',
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
        all_games=all_games,
        all_tournaments=all_tournaments,
        selected_ids=selected_ids,
    )


@app.route('/film/games')
@login_required
def games_list():
    current_user = get_current_user()
    games = Game.query.options(joinedload(Game.tournament)).all()

    tournaments_map = {}
    standalone_games = []

    for game in games:
        if game.tournament:
            tournament_id = game.tournament.id
            if tournament_id not in tournaments_map:
                tournaments_map[tournament_id] = {
                    'tournament': game.tournament,
                    'games': []
                }
            tournaments_map[tournament_id]['games'].append(game)
        else:
            standalone_games.append(game)

    def game_chronological_sort_key(game):
        return (
            game.game_date or '9999-12-31',
            game.tournament_game_number if game.tournament_game_number is not None else 999999,
            game.id
        )

    tournament_sections = list(tournaments_map.values())
    for section in tournament_sections:
        section['games'].sort(key=game_chronological_sort_key)

    def tournament_recent_first_key(section):
        tournament = section['tournament']
        latest_game_date = max((g.game_date or '' for g in section['games']), default='')
        primary_date = tournament.start_date or latest_game_date
        return (primary_date, tournament.id)

    tournament_sections.sort(key=tournament_recent_first_key, reverse=True)
    standalone_games.sort(key=lambda g: (g.game_date or '', g.id), reverse=True)

    return render_template(
        'film_room/pages/games_list.html',
        current_user=current_user,
        tournament_sections=tournament_sections,
        standalone_games=standalone_games
    )


@app.route('/film/app')
@login_required
def film_room_app():
    current_user = get_current_user()
    return render_template(
        'film_room/pages/film_room_app.html',
        current_user=current_user,
        initial_game_id=None,
    )


@app.route('/film/app/games/<int:game_id>')
@login_required
def film_room_app_game(game_id):
    current_user = get_current_user()
    # Validate game exists so we can return a 404 in Flask instead of a client-side fetch failure.
    Game.query.get_or_404(game_id)
    return render_template(
        'film_room/pages/film_room_app.html',
        current_user=current_user,
        initial_game_id=game_id,
    )


@app.route('/film/tournaments/new', methods=['GET', 'POST'])
@admin_required
def new_tournament():
    current_user = get_current_user()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        start_date = request.form.get('start_date', '').strip()

        if not name:
            flash('Tournament name is required.', 'error')
            return render_template('film_room/forms/new_tournament.html', current_user=current_user)

        tournament = Tournament(
            name=name,
            start_date=start_date if start_date else None
        )

        try:
            db.session.add(tournament)
            db.session.commit()
            flash(f'Tournament "{name}" created successfully!', 'success')
            return redirect(url_for('new_game'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating tournament: {str(e)}', 'error')
            return render_template('film_room/forms/new_tournament.html', current_user=current_user)

    return render_template('film_room/forms/new_tournament.html', current_user=current_user)


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
            player_sheet_data['point_players'][point.point_index] = sorted(
                [p.name for p in point.players],
                key=lambda n: all_players.index(n) if n in all_players else len(all_players)
            )
    
    users = [u.username for u in User.query.order_by(User.username).all()]
    return render_template('film_room/pages/game_player.html', current_user=current_user, game=game, player_sheet_data=player_sheet_data, point_field_options=point_field_options, users=users)


@app.route('/film/games/new', methods=['GET', 'POST'])
@admin_required
def new_game():
    current_user = get_current_user()
    tournaments = Tournament.query.order_by(Tournament.start_date.desc().nullslast(), Tournament.name.asc()).all()
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        opponent = request.form.get('opponent', '').strip()
        youtube_id = request.form.get('youtube_id', '').strip()
        game_date = request.form.get('game_date', '').strip()
        tournament_id_raw = request.form.get('tournament_id', '').strip()
        tournament_game_number_raw = request.form.get('tournament_game_number', '').strip()
        final_score_tron = request.form.get('final_score_tron', '').strip()
        final_score_opponent = request.form.get('final_score_opponent', '').strip()
        
        # Validate required fields
        if not title or not opponent:
            flash('Title and opponent are required.', 'error')
            return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)

        tournament = None
        if tournament_id_raw:
            try:
                tournament = Tournament.query.get(int(tournament_id_raw))
            except ValueError:
                flash('Invalid tournament selection.', 'error')
                return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)
            if not tournament:
                flash('Selected tournament not found.', 'error')
                return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)

        if tournament and not tournament_game_number_raw:
            flash('Game number is required when a tournament is selected.', 'error')
            return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)
        if not tournament and tournament_game_number_raw:
            flash('Choose a tournament before setting a tournament game number.', 'error')
            return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)

        tournament_game_number = None
        if tournament_game_number_raw:
            try:
                tournament_game_number = int(tournament_game_number_raw)
                if tournament_game_number <= 0:
                    raise ValueError
            except ValueError:
                flash('Tournament game number must be a positive whole number.', 'error')
                return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)
        
        # Convert scores to integers if provided
        tron_score = int(final_score_tron) if final_score_tron else None
        opp_score = int(final_score_opponent) if final_score_opponent else None
        
        # Create new game
        new_game = Game(
            title=title,
            opponent=opponent,
            youtube_id=youtube_id if youtube_id else None,
            game_date=game_date if game_date else None,
            tournament_id=tournament.id if tournament else None,
            tournament_game_number=tournament_game_number,
            final_score_tron=tron_score,
            final_score_opponent=opp_score
        )
        
        try:
            db.session.add(new_game)
            db.session.commit()
            flash(f'Game "{title}" created successfully!', 'success')
            return redirect(url_for('games_list'))  # Redirect to player page for now
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating game: {str(e)}', 'error')
            return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)
    
    # GET request - show the form
    return render_template('film_room/forms/new_game.html', current_user=current_user, tournaments=tournaments)


@app.route('/film/games/<int:game_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_game(game_id):
    current_user = get_current_user()
    
    game = Game.query.get_or_404(game_id)
    tournaments = Tournament.query.order_by(Tournament.start_date.desc().nullslast(), Tournament.name.asc()).all()
    
    if request.method == 'POST':
        # Get form data
        title = request.form.get('title', '').strip()
        opponent = request.form.get('opponent', '').strip()
        youtube_id = request.form.get('youtube_id', '').strip()
        game_date = request.form.get('game_date', '').strip()
        tournament_id_raw = request.form.get('tournament_id', '').strip()
        tournament_game_number_raw = request.form.get('tournament_game_number', '').strip()
        final_score_tron = request.form.get('final_score_tron', '').strip()
        final_score_opponent = request.form.get('final_score_opponent', '').strip()
        
        # Validate required fields
        if not title or not opponent:
            flash('Title and opponent are required.', 'error')
            return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)

        tournament = None
        if tournament_id_raw:
            try:
                tournament = Tournament.query.get(int(tournament_id_raw))
            except ValueError:
                flash('Invalid tournament selection.', 'error')
                return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)
            if not tournament:
                flash('Selected tournament not found.', 'error')
                return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)

        if tournament and not tournament_game_number_raw:
            flash('Game number is required when a tournament is selected.', 'error')
            return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)
        if not tournament and tournament_game_number_raw:
            flash('Choose a tournament before setting a tournament game number.', 'error')
            return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)

        tournament_game_number = None
        if tournament_game_number_raw:
            try:
                tournament_game_number = int(tournament_game_number_raw)
                if tournament_game_number <= 0:
                    raise ValueError
            except ValueError:
                flash('Tournament game number must be a positive whole number.', 'error')
                return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)
        
        # Convert scores to integers if provided
        tron_score = int(final_score_tron) if final_score_tron else None
        opp_score = int(final_score_opponent) if final_score_opponent else None
        
        # Update game fields
        game.title = title
        game.opponent = opponent
        game.youtube_id = youtube_id if youtube_id else None
        game.game_date = game_date if game_date else None
        game.tournament_id = tournament.id if tournament else None
        game.tournament_game_number = tournament_game_number
        game.final_score_tron = tron_score
        game.final_score_opponent = opp_score
        
        try:
            db.session.commit()
            flash(f'Game "{title}" updated successfully!', 'success')
            return redirect(url_for('view_game', game_id=game.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating game: {str(e)}', 'error')
            return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)
    
    # GET request - show the form
    return render_template('film_room/forms/edit_game.html', current_user=current_user, game=game, tournaments=tournaments)


# =========================
# COMMENTS API
# =========================

@app.route('/film/api/games/<int:game_id>/comments', methods=['GET'])
@login_required
def get_comments(game_id):
    """Get all comments for a game"""
    game = Game.query.get_or_404(game_id)
    current_user = get_current_user()
    viewer_username = current_user.username if current_user else None

    # Sort by timestamp (nulls last), then by created_at for comments without timestamps
    comments = Comment.query.filter_by(game_id=game_id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc()
    ).all()
    
    def can_see(comment):
        """Return True if the current viewer is allowed to see this comment."""
        if not comment.private_to:
            return True  # public comment (private_to IS NULL)
        if viewer_username is None:
            return False
        try:
            allowed = json.loads(comment.private_to)
        except (ValueError, TypeError):
            allowed = []
        # Direct access: author or explicitly listed recipient
        if viewer_username == comment.author_name or viewer_username in allowed:
            return True
        # Leadership visibility rule: if the author is leadership and the comment
        # was sent to at least one specific person, all leadership members can see it.
        if allowed and current_user and current_user.is_leadership:
            author_user = User.query.filter_by(username=comment.author_name).first()
            if author_user and author_user.is_leadership:
                return True
        return False

    comments_list = []
    for comment in comments:
        if not can_see(comment):
            continue
        private_to_list = None
        if comment.private_to:
            try:
                private_to_list = json.loads(comment.private_to)
            except (ValueError, TypeError):
                private_to_list = []
        comment_author = User.query.filter_by(username=comment.author_name).first()
        comment_data = {
            'id': comment.id,
            'author_name': comment.author_name,
            'is_leadership': bool(comment_author and comment_author.is_leadership),
            'content': comment.content,
            'comment_type': comment.comment_type,
            'timestamp': comment.timestamp,
            'created_at': fmt_dt_est(comment.created_at),
            'private_to': private_to_list,
            'replies': []
        }
        
        # Get replies (1-level nesting)
        replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at.asc()).all()
        for reply in replies:
            if not can_see(reply):
                continue
            reply_private_to = None
            if reply.private_to:
                try:
                    reply_private_to = json.loads(reply.private_to)
                except (ValueError, TypeError):
                    reply_private_to = []
            reply_author = User.query.filter_by(username=reply.author_name).first()
            comment_data['replies'].append({
                'id': reply.id,
                'author_name': reply.author_name,
                'is_leadership': bool(reply_author and reply_author.is_leadership),
                'content': reply.content,
                'created_at': fmt_dt_est(reply.created_at),
                'private_to': reply_private_to
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
    private_to_raw = data.get('private_to')  # list of usernames or None

    # Normalize private_to to a JSON string or None.
    # An empty list [] means "private to author only"; None means public.
    if private_to_raw is not None and isinstance(private_to_raw, list):
        private_to_stored = json.dumps([u.strip() for u in private_to_raw if isinstance(u, str) and u.strip()])
    else:
        private_to_stored = None

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
        content=content,
        private_to=private_to_stored
    )
    
    try:
        db.session.add(new_comment)
        db.session.flush()  # get new_comment.id before commit

        # Create notifications for mentions / private recipients
        _create_notifications_for_comment(
            new_comment,
            game_id,
            author_name,
            bool(current_user and current_user.is_leadership)
        )

        db.session.commit()

        private_to_list = json.loads(private_to_stored) if private_to_stored else None
        return jsonify({
            'success': True,
            'comment': {
                'id': new_comment.id,
                'author_name': new_comment.author_name,
                'is_leadership': bool(current_user and current_user.is_leadership),
                'content': new_comment.content,
                'comment_type': new_comment.comment_type,
                'timestamp': new_comment.timestamp,
                'created_at': fmt_dt_est(new_comment.created_at),
                'parent_id': new_comment.parent_id,
                'private_to': private_to_list
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
    private_to_raw = data.get('private_to', '__unchanged__')  # sentinel to detect omission

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
        # Update private_to only if key was present in the request
        if private_to_raw != '__unchanged__':
            if private_to_raw is not None and isinstance(private_to_raw, list):
                comment.private_to = json.dumps([u.strip() for u in private_to_raw if isinstance(u, str) and u.strip()])
            else:
                comment.private_to = None

        # Recalculate notifications: wipe existing rows then recreate
        CommentNotification.query.filter_by(comment_id=comment.id).delete()
        _create_notifications_for_comment(
            comment,
            comment.game_id,
            current_user.username,
            current_user.is_leadership
        )

        db.session.commit()

        private_to_list = None
        if comment.private_to:
            try:
                private_to_list = json.loads(comment.private_to)
            except (ValueError, TypeError):
                private_to_list = []
        return jsonify({
            'success': True,
            'comment': {
                'id': comment.id,
                'content': comment.content,
                'author_name': comment.author_name,
                'comment_type': comment.comment_type,
                'timestamp': comment.timestamp,
                'created_at': fmt_dt_est(comment.created_at),
                'parent_id': comment.parent_id,
                'private_to': private_to_list
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
            return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)
        
        if not file.filename.endswith('.csv'):
            flash('Please upload a CSV file.', 'error')
            return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            rows = list(csv_reader)
            
            if len(rows) < 4:
                flash('CSV file must have at least 4 rows (O/D row, TRON row, Enemy row, and player rows).', 'error')
                return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)
            
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
            return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)
    
    # GET request - show upload form
    return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)


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
        if 'not_filmed' in data:
            point.not_filmed = bool(data['not_filmed'])
        
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
        playback_position = data.get('playback_position')  # Current video position in seconds
        
        if seconds_watched <= 0 and playback_position is None:
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
                watch_duration_seconds=max(0, seconds_watched)
            )
            db.session.add(watch_session)
        else:
            # Update existing session
            if seconds_watched > 0:
                watch_session.watch_duration_seconds += seconds_watched
            watch_session.last_updated = datetime.utcnow()
        
        # Always update last known playback position
        if playback_position is not None:
            watch_session.last_position_seconds = playback_position
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'session_id': watch_session.id,
            'total_watched': watch_session.watch_duration_seconds
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/film/api/games/<int:game_id>/watch-progress', methods=['GET'])
@login_required
def get_watch_progress(game_id):
    """Get the last saved playback position for this user and game"""
    current_user = get_current_user()
    Game.query.get_or_404(game_id)
    
    # Find the most recently updated session for this user+game
    session = VideoWatchSession.query.filter_by(
        user_id=current_user.id,
        game_id=game_id
    ).order_by(VideoWatchSession.last_updated.desc()).first()
    
    last_position = None
    if session and session.last_position_seconds and session.last_position_seconds > 30:
        last_position = session.last_position_seconds
    
    return jsonify({'last_position': last_position})


@app.route('/film/analytics')
@admin_required
def analytics_dashboard():
    """Admin analytics dashboard showing user engagement metrics"""
    current_user = get_current_user()
    
    # Get all users
    users = User.query.all()

    # Pre-compute leadership usernames (excludes admin-only users)
    leadership_usernames = set(
        u.username for u in User.query.filter(
            User.is_leadership == True
        ).all()
    )

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

        # Leadership notifications: comments sent to this user by leadership/admin
        _ldr_q = (
            CommentNotification.query
            .join(Comment, CommentNotification.comment_id == Comment.id)
            .filter(
                CommentNotification.recipient_username == user.username,
                Comment.author_name.in_(leadership_usernames),
            )
        )
        leadership_notif_total = _ldr_q.count()
        leadership_notif_read  = _ldr_q.filter(CommentNotification.is_read == True).count()

        user_analytics.append({
            'user': user,
            'login_count': login_count,
            'total_watch_minutes': round(total_watch_minutes, 1),
            'game_breakdown': game_breakdown,
            'comment_count': comment_count,
            'leadership_notif_total': leadership_notif_total,
            'leadership_notif_read':  leadership_notif_read,
        })
    
    # Sort by total watch minutes (most engaged users first)
    user_analytics.sort(key=lambda x: x['total_watch_minutes'], reverse=True)
    
    # Calculate totals
    total_unique_users = len([u for u in user_analytics if u['login_count'] > 0])
    total_watch_minutes = sum([u['total_watch_minutes'] for u in user_analytics])
    total_comments = sum([u['comment_count'] for u in user_analytics])
    
    return render_template('film_room/pages/analytics_dashboard.html', 
                          current_user=current_user,
                          user_analytics=user_analytics,
                          total_unique_users=total_unique_users,
                          total_watch_minutes=round(total_watch_minutes, 1),
                          total_comments=total_comments)


# =========================
# NOTIFICATION ENDPOINTS
# =========================

@app.route('/film/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    """Return the current user's notifications (newest first, max 50)."""
    current_user = get_current_user()
    notifs = (
        CommentNotification.query
        .filter_by(recipient_username=current_user.username)
        .order_by(CommentNotification.created_at.desc())
        .limit(50)
        .all()
    )

    result = []
    for n in notifs:
        snippet = ''
        if n.comment:
            raw = n.comment.content
            snippet = (raw[:100] + '…') if len(raw) > 100 else raw
        result.append({
            'id': n.id,
            'comment_id': n.comment_id,
            'game_id': n.game_id,
            'game_title': n.game.title if n.game else '',
            'notification_type': n.notification_type,
            'is_read': n.is_read,
            'created_at': fmt_dt_est(n.created_at),
            'created_at_iso': n.created_at.isoformat() + 'Z' if n.created_at else '',
            'author_name': n.comment.author_name if n.comment else '',
            'content_snippet': snippet,
            'comment_timestamp': n.comment.timestamp if n.comment else None,
            'comment_parent_id': n.comment.parent_id if n.comment else None,
        })

    unread_count = sum(1 for r in result if not r['is_read'])
    return jsonify({'notifications': result, 'unread_count': unread_count})


@app.route('/film/api/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """Mark a single notification as read and record the timestamp for analytics."""
    current_user = get_current_user()
    notif = CommentNotification.query.filter_by(
        id=notif_id, recipient_username=current_user.username
    ).first_or_404()
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.utcnow()
        db.session.commit()
    return jsonify({'success': True})


@app.route('/film/api/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all unread notifications for the current user as read."""
    current_user = get_current_user()
    now = datetime.utcnow()
    CommentNotification.query.filter_by(
        recipient_username=current_user.username, is_read=False
    ).update({'is_read': True, 'read_at': now})
    db.session.commit()
    return jsonify({'success': True})


@app.route('/film/api/user/<username>/comments')
@admin_required
def user_comment_list(username):
    """Return comments written by a user (newest first).
    Private comments are only visible if: they are public, the author is leadership/admin,
    or the current admin is a recipient in private_to.
    For replies, the parent comment's privacy is also checked — if the admin can't see
    the parent thread, the reply is hidden too."""
    current_user = get_current_user()

    leadership_usernames = set(
        u.username for u in User.query.filter(
            db.or_(User.is_leadership == True, User.is_admin == True)
        ).all()
    )
    author_is_leadership = username in leadership_usernames

    ParentComment = db.aliased(Comment)

    rows = (
        db.session.query(
            Comment.id,
            Comment.content,
            Comment.timestamp,
            Comment.created_at,
            Comment.game_id,
            Comment.parent_id,
            Comment.private_to,
            ParentComment.private_to.label('parent_private_to'),
            ParentComment.author_name.label('parent_author_name'),
            Game.title.label('game_title'),
            Game.opponent.label('game_opponent'),
        )
        .join(Game, Comment.game_id == Game.id)
        .outerjoin(ParentComment, Comment.parent_id == ParentComment.id)
        .filter(Comment.author_name == username)
        .order_by(Comment.created_at.desc())
        .all()
    )

    def _admin_can_see_private(private_to_raw, author_name):
        """Return (visible, parsed_list). visible=True if the admin can see a comment
        with this private_to value written by author_name."""
        if private_to_raw is None:
            return True, None
        try:
            pt_list = json.loads(private_to_raw)
        except Exception:
            pt_list = []
        author_is_ldr = author_name in leadership_usernames
        if not author_is_ldr and current_user.username not in pt_list:
            return False, pt_list
        return True, pt_list

    result = []
    for r in rows:
        # Check own comment's privacy
        own_visible, private_to_list = _admin_can_see_private(r.private_to, username)
        if not own_visible:
            continue

        # For replies, also check parent thread privacy
        if r.parent_id is not None and r.parent_private_to is not None:
            parent_visible, _ = _admin_can_see_private(r.parent_private_to, r.parent_author_name or '')
            if not parent_visible:
                continue

        result.append({
            'id': r.id,
            'content': r.content,
            'timestamp': r.timestamp,
            'created_at': fmt_dt_est(r.created_at),
            'created_at_iso': r.created_at.isoformat() + 'Z' if r.created_at else '',
            'game_id': r.game_id,
            'is_reply': r.parent_id is not None,
            'game_title': r.game_title,
            'game_opponent': r.game_opponent,
            'private_to': private_to_list,
        })

    return jsonify({'username': username, 'comments': result})


@app.route('/film/api/user/<username>/leadership-tags')
@admin_required
def user_leadership_tags(username):
    """Return all notifications received by a user that were triggered by leadership comments (excludes admin-only)."""
    leadership_usernames = set(
        u.username for u in User.query.filter(
            User.is_leadership == True
        ).all()
    )
    rows = (
        db.session.query(
            CommentNotification.id.label('notif_id'),
            CommentNotification.is_read,
            CommentNotification.notification_type,
            CommentNotification.created_at,
            Comment.id.label('comment_id'),
            Comment.content,
            Comment.timestamp,
            Comment.author_name,
            Comment.game_id,
            Comment.parent_id,
            Comment.private_to,
            Game.title.label('game_title'),
            Game.opponent.label('game_opponent'),
        )
        .join(Comment, CommentNotification.comment_id == Comment.id)
        .join(Game, Comment.game_id == Game.id)
        .filter(
            CommentNotification.recipient_username == username,
            Comment.author_name.in_(leadership_usernames),
        )
        .order_by(CommentNotification.created_at.desc())
        .all()
    )
    return jsonify({
        'username': username,
        'tags': [
            {
                'notif_id': r.notif_id,
                'is_read': r.is_read,
                'notification_type': r.notification_type,
                'comment_id': r.comment_id,
                'content': r.content,
                'timestamp': r.timestamp,
                'created_at_iso': r.created_at.isoformat() + 'Z' if r.created_at else '',
                'author_name': r.author_name,
                'game_id': r.game_id,
                'is_reply': r.parent_id is not None,
                'game_title': r.game_title,
                'game_opponent': r.game_opponent,
                'private_to': (json.loads(r.private_to) if r.private_to else None),
            }
            for r in rows
        ]
    })
