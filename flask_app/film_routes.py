from flask import flash, jsonify, redirect, render_template, request, session, url_for
from datetime import datetime

from . import app, db
from .models import Player, Game, Point, point_players
from .utils import get_current_user

@app.route('/player')
def player():
    current_user = get_current_user()
    return render_template('player.html', current_user=current_user)


@app.route('/games')
def games_list():
    current_user = get_current_user()
    games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()
    return render_template('games_list.html', current_user=current_user, games=games)


@app.route('/games/<int:game_id>')
def view_game(game_id):
    current_user = get_current_user()
    game = Game.query.get_or_404(game_id)
    return render_template('game_player.html', current_user=current_user, game=game)


@app.route('/film/games/new_game', methods=['GET', 'POST'])
def new_game():
    current_user = get_current_user()
    
    # Check if user is admin
    if not current_user or not current_user.is_admin:
        flash('You must be an admin to create games.', 'error')
        return redirect(url_for('index'))
    
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


@app.route('/games/<int:game_id>/edit', methods=['GET', 'POST'])
def edit_game(game_id):
    current_user = get_current_user()
    
    # Check if user is admin
    if not current_user or not current_user.is_admin:
        flash('You must be an admin to edit games.', 'error')
        return redirect(url_for('index'))
    
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