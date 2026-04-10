from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash
from sqlalchemy import func
from sqlalchemy.orm import joinedload
import csv
import io
import json
import os

from . import app, db
from .models import Player, Game, Point, Tournament, User, Comment, GameWatched
from .utils import get_current_user, login_required, admin_required
from .film_helpers import fmt_dt_est


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


@app.route('/film/my-games', endpoint='my_games')
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
        if not current_user.is_admin:
            my_games_list = [g for g in my_games_list if not g.is_hidden]
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


@app.route('/film/data', endpoint='tron_data')
@login_required
def tron_data():
    """Team-wide game data and statistics page."""
    current_user = get_current_user()

    all_games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()
    if not current_user.is_admin:
        all_games = [g for g in all_games if not g.is_hidden]
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


@app.route('/film/games', endpoint='games_list')
@login_required
def games_list():
    current_user = get_current_user()
    games = Game.query.options(joinedload(Game.tournament)).all()
    if not current_user.is_admin:
        games = [g for g in games if not g.is_hidden]

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

    watched_rows = GameWatched.query.filter_by(user_id=current_user.id).all()
    watched_game_ids = {row.game_id for row in watched_rows}

    return render_template(
        'film_room/pages/games_list.html',
        current_user=current_user,
        tournament_sections=tournament_sections,
        standalone_games=standalone_games,
        watched_game_ids=watched_game_ids
    )


@app.route('/film/games/<int:game_id>', endpoint='view_game')
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

        # Only build the player sheet if there are actual players
        # (after a "clear" deletion, all_players will be empty and we fall back to Upload CSV)
        if all_players:
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

            # Build injury sub lookups for the template and JS
            player_sheet_data['point_injury_subs'] = {}
            player_sheet_data['point_players_js'] = {}
            for point in points:
                subs = point.injury_subs or {}
                sub_off_set = set(subs.get('off', []))
                sub_on_set = set(subs.get('on', []))
                player_sheet_data['point_injury_subs'][point.point_index] = subs
                player_sheet_data['point_players_js'][point.point_index] = [
                    {
                        'name': n,
                        'sub': 'off' if n in sub_off_set else ('on' if n in sub_on_set else None)
                    }
                    for n in player_sheet_data['point_players'][point.point_index]
                ]

    users = [u.username for u in User.query.order_by(User.username).all()]
    is_watched = GameWatched.query.filter_by(user_id=current_user.id, game_id=game_id).first() is not None
    return render_template('film_room/pages/game_player.html', current_user=current_user, game=game, player_sheet_data=player_sheet_data, point_field_options=point_field_options, users=users, is_watched=is_watched)


@app.route('/film/games/new', methods=['GET', 'POST'], endpoint='new_game')
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
        is_hidden = request.form.get('is_hidden') == 'on'
        new_game = Game(
            title=title,
            opponent=opponent,
            youtube_id=youtube_id if youtube_id else None,
            game_date=game_date if game_date else None,
            tournament_id=tournament.id if tournament else None,
            tournament_game_number=tournament_game_number,
            final_score_tron=tron_score,
            final_score_opponent=opp_score,
            is_hidden=is_hidden
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


@app.route('/film/games/<int:game_id>/edit', methods=['GET', 'POST'], endpoint='edit_game')
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
        game.is_hidden = request.form.get('is_hidden') == 'on'

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


@app.route('/film/tournaments/new', methods=['GET', 'POST'], endpoint='new_tournament')
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


@app.route('/film/games/<int:game_id>/upload_csv', methods=['GET', 'POST'], endpoint='upload_game_csv')
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

            # Build a map of existing points by index so we can reuse them
            # (preserves timestamp_start, not_filmed, pull_play, etc.)
            existing_points = {
                p.point_index: p
                for p in Point.query.filter_by(game_id=game_id).all()
            }

            # Clear roster; we'll rebuild it from the CSV
            game.roster.clear()
            db.session.flush()

            # Track all players in this game for roster
            roster_players = set()
            valid_point_indices = set()

            # Create or update points
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

                valid_point_indices.add(point_idx)

                # Reuse existing point (preserving timestamp, not_filmed, etc.) or create new
                if point_idx in existing_points:
                    point = existing_points[point_idx]
                    point.tron_o = tron_o
                    point.tron_point = tron_point
                    # Clear existing player associations before re-adding from CSV
                    point.players = []
                    db.session.flush()
                else:
                    point = Point(
                        game_id=game_id,
                        point_index=point_idx,
                        tron_o=tron_o,
                        tron_point=tron_point
                    )
                    db.session.add(point)
                    db.session.flush()  # Get point.id

                # Track players added to this point to avoid duplicates
                added_players = set()

                # Track injury sub players for this point
                sub_off_players = []  # players who were subbed off during an injury timeout
                sub_on_players = []   # players who were subbed on during an injury timeout

                # Add players to point
                for player_row in player_rows:
                    if not player_row:
                        continue

                    player_name = player_row[0].strip()
                    if not player_name:
                        continue

                    # Check if player participated in this point
                    cell_val = player_row[col_idx].strip() if col_idx < len(player_row) else ''
                    if cell_val:
                        # Parse injury substitution notation:
                        #   "N/"  => player was subbed OFF during an injury timeout
                        #   "/N"  => player was subbed ON during an injury timeout
                        is_sub_off = cell_val.endswith('/') and not cell_val.startswith('/')
                        is_sub_on = cell_val.startswith('/') and not cell_val.endswith('/')

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

                        # Track sub status
                        if is_sub_off:
                            sub_off_players.append(player_name)
                        elif is_sub_on:
                            sub_on_players.append(player_name)

                # Store injury sub data on the point
                if sub_off_players or sub_on_players:
                    point.injury_subs = {'off': sub_off_players, 'on': sub_on_players}
                else:
                    point.injury_subs = None

            # Delete any stale points not present in the new CSV
            for idx, stale_point in existing_points.items():
                if idx not in valid_point_indices:
                    db.session.delete(stale_point)

            # Update game roster
            for player in roster_players:
                game.roster.append(player)

            # Store player order data
            game.player_order_data = {
                'players': player_names_ordered,
                'separator_index': separator_index
            }

            db.session.commit()
            flash(f'Successfully uploaded game data! Created/updated {num_points} points with player assignments.', 'success')
            return redirect(url_for('view_game', game_id=game.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error processing CSV: {str(e)}', 'error')
            return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)

    # GET request - show upload form
    return render_template('film_room/forms/upload_game_csv.html', current_user=current_user, game=game)


@app.route('/film/games/<int:game_id>/delete_player_sheet', methods=['POST'], endpoint='delete_player_sheet')
@admin_required
def delete_player_sheet(game_id):
    """Clear player sheet assignments without deleting point/timestamp data."""
    current_user = get_current_user()

    game = Game.query.get_or_404(game_id)

    try:
        # Remove all player↔point associations while keeping the points themselves
        # (preserves timestamp_start, not_filmed, pull_play, etc.)
        for point in game.points:
            point.players = []

        # Clear the game roster and stored player order
        game.roster.clear()
        game.player_order_data = None

        db.session.commit()
        flash('Player sheet cleared. Timestamps and point data are preserved. You can now upload a new CSV.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error clearing player sheet: {str(e)}', 'error')

    return redirect(url_for('view_game', game_id=game.id))


@app.route('/film/analytics', endpoint='analytics_dashboard')
@admin_required
def analytics_dashboard():
    """Admin analytics dashboard showing user engagement metrics"""
    from .models import VideoWatchSession, LoginEvent, CommentNotification
    from sqlalchemy import func
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

        watched_count = GameWatched.query.filter_by(user_id=user.id).count()

        user_analytics.append({
            'user': user,
            'login_count': login_count,
            'total_watch_minutes': round(total_watch_minutes, 1),
            'game_breakdown': game_breakdown,
            'comment_count': comment_count,
            'leadership_notif_total': leadership_notif_total,
            'leadership_notif_read':  leadership_notif_read,
            'watched_count': watched_count,
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
