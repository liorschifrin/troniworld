from flask import flash, jsonify, redirect, render_template, request, session, url_for
from datetime import datetime
import csv
import io

from . import app, db
from .models import Player, Game, Point, Event, Comment, point_players
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
    
    # Prepare player sheet data if points exist
    player_sheet_data = None
    points = game.points.order_by(Point.point_index).all()
    
    if points:
        # Get all unique players across all points, maintaining roster order if available
        all_players = []
        if game.roster:
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
            'point_players': {}  # Map of point_index -> [player_names]
        }
        
        for point in points:
            player_sheet_data['point_players'][point.point_index] = [p.name for p in point.players]
    
    return render_template('game_player.html', current_user=current_user, game=game, player_sheet_data=player_sheet_data)


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


# =========================
# COMMENTS API
# =========================

@app.route('/api/games/<int:game_id>/comments', methods=['GET'])
def get_comments(game_id):
    """Get all comments for a game"""
    game = Game.query.get_or_404(game_id)
    comments = Comment.query.filter_by(game_id=game_id, parent_id=None).order_by(Comment.created_at.desc()).all()
    
    comments_list = []
    for comment in comments:
        comment_data = {
            'id': comment.id,
            'author_name': comment.author_name,
            'content': comment.content,
            'comment_type': comment.comment_type,
            'timestamp': comment.timestamp,
            'created_at': comment.created_at.strftime('%b %d, %Y %I:%M %p'),
            'replies': []
        }
        
        # Get replies (1-level nesting)
        replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at.asc()).all()
        for reply in replies:
            comment_data['replies'].append({
                'id': reply.id,
                'author_name': reply.author_name,
                'content': reply.content,
                'created_at': reply.created_at.strftime('%b %d, %Y %I:%M %p')
            })
        
        comments_list.append(comment_data)
    
    return jsonify({'comments': comments_list})


@app.route('/api/games/<int:game_id>/comments', methods=['POST'])
def create_comment(game_id):
    """Create a new comment for a game"""
    game = Game.query.get_or_404(game_id)
    
    data = request.get_json()
    content = data.get('content', '').strip()
    author_name = data.get('author_name', 'Anonymous').strip()
    comment_type = data.get('comment_type', 'Comment')
    parent_id = data.get('parent_id')
    timestamp = data.get('timestamp')
    point_id = data.get('point_id')
    
    if not content:
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
                'created_at': new_comment.created_at.strftime('%b %d, %Y %I:%M %p'),
                'parent_id': new_comment.parent_id
            }
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/games/<int:game_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(game_id, comment_id):
    """Delete a comment"""
    current_user = get_current_user()
    
    # Must be logged in to delete comments
    if not current_user:
        return jsonify({'error': 'Must be logged in to delete comments'}), 401
    
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    
    # Only admins or comment author can delete (for now, all users post as "Tron User")
    # In a real app, you'd track user_id on comments
    if not current_user.is_admin:
        # For now, only admins can delete since we don't track comment ownership
        return jsonify({'error': 'Only admins can delete comments'}), 403
    
    try:
        db.session.delete(comment)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# =========================
# CSV UPLOAD FOR GAME DATA
# =========================

@app.route('/games/<int:game_id>/upload_csv', methods=['GET', 'POST'])
def upload_game_csv(game_id):
    """Upload CSV to populate game points and player data"""
    current_user = get_current_user()
    
    # Check if user is admin
    if not current_user or not current_user.is_admin:
        flash('You must be an admin to upload game data.', 'error')
        return redirect(url_for('index'))
    
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
            player_rows = []
            for row in rows[player_start_idx:]:
                if row and row[0].strip().upper() == 'END PLAYERS':
                    break
                player_rows.append(row)
            
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
                        
                        # Add player to point
                        point.players.append(player)
                        added_players.add(player_name)
                        roster_players.add(player)
            
            # Update game roster (already cleared at the start)
            for player in roster_players:
                game.roster.append(player)
            
            db.session.commit()
            flash(f'Successfully uploaded game data! Created {num_points} points with player assignments.', 'success')
            return redirect(url_for('view_game', game_id=game.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing CSV: {str(e)}', 'error')
            return render_template('upload_game_csv.html', current_user=current_user, game=game)
    
    # GET request - show upload form
    return render_template('upload_game_csv.html', current_user=current_user, game=game)


@app.route('/games/<int:game_id>/delete_player_sheet', methods=['POST'])
def delete_player_sheet(game_id):
    """Delete all points and player associations for a game"""
    current_user = get_current_user()
    
    # Check if user is admin
    if not current_user or not current_user.is_admin:
        flash('You must be an admin to delete game data.', 'error')
        return redirect(url_for('index'))
    
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