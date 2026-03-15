from flask import jsonify, request
from datetime import datetime
import json
import re

from sqlalchemy.orm.attributes import flag_modified

from . import app, db
from .models import Comment, Game, Point, User, VideoWatchSession, CommentNotification, GameWatched
from .utils import get_current_user, login_required, admin_required
from .film_helpers import fmt_dt_est


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
        parent = db.session.get(Comment, comment.parent_id)
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


@app.route('/film/api/games/<int:game_id>/comments', methods=['GET'], endpoint='get_comments')
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


@app.route('/film/api/games/<int:game_id>/comments', methods=['POST'], endpoint='create_comment')
@login_required
def create_comment(game_id):
    """Create a new comment for a game"""
    game = Game.query.get_or_404(game_id)

    # Get the current user
    current_user = get_current_user()

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400

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


@app.route('/film/api/games/<int:game_id>/comments/<int:comment_id>', methods=['DELETE'], endpoint='delete_comment')
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


@app.route('/film/api/games/<int:game_id>/comments/<int:comment_id>', methods=['PATCH'], endpoint='update_comment')
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


@app.route('/film/api/games/<int:game_id>/points/<int:point_id>', methods=['PATCH'], endpoint='update_point')
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


@app.route('/film/api/games/<int:game_id>/update_player_sheet', methods=['POST'], endpoint='update_player_sheet')
@admin_required
def update_player_sheet(game_id):
    """Bulk-update player↔point assignments without re-uploading the CSV."""
    game = Game.query.get_or_404(game_id)
    data = request.get_json() or {}
    changes = data.get('changes', [])

    try:
        for change in changes:
            point_id = change.get('point_id')
            player_name = change.get('player_name', '').strip()
            in_point = bool(change.get('in_point'))

            if not point_id or not player_name:
                continue

            point = Point.query.filter_by(id=point_id, game_id=game_id).first()
            if not point:
                continue

            from .models import Player
            player = Player.query.filter_by(name=player_name).first()
            if not player:
                continue

            sub_status = change.get('sub_status')  # null | "off" | "on"

            if in_point:
                if player not in point.players:
                    point.players.append(player)
                # Ensure the player is also on the game roster
                if player not in game.roster:
                    game.roster.append(player)
            else:
                if player in point.players:
                    point.players.remove(player)
                sub_status = None  # removed players have no sub status

            # Update injury_subs for this point based on sub_status change
            subs = dict(point.injury_subs) if point.injury_subs else {'off': [], 'on': []}
            # Remove player from both lists first
            subs['off'] = [n for n in subs.get('off', []) if n != player_name]
            subs['on'] = [n for n in subs.get('on', []) if n != player_name]
            if sub_status == 'off':
                subs['off'].append(player_name)
            elif sub_status == 'on':
                subs['on'].append(player_name)
            point.injury_subs = subs if (subs['off'] or subs['on']) else None
            # Mark the JSON column as modified so SQLAlchemy detects the change
            flag_modified(point, 'injury_subs')

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/film/api/games/<int:game_id>/track-watch-time', methods=['POST'], endpoint='track_watch_time')
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


@app.route('/film/api/games/<int:game_id>/watch-progress', methods=['GET'], endpoint='get_watch_progress')
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


@app.route('/film/api/notifications', methods=['GET'], endpoint='get_notifications')
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


@app.route('/film/api/notifications/<int:notif_id>/read', methods=['POST'], endpoint='mark_notification_read')
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


@app.route('/film/api/notifications/read-all', methods=['POST'], endpoint='mark_all_notifications_read')
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


@app.route('/film/api/user/<username>/comments', endpoint='user_comment_list')
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


@app.route('/film/api/user/<username>/leadership-tags', endpoint='user_leadership_tags')
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


@app.route('/film/api/games/<int:game_id>/toggle-watched', methods=['POST'], endpoint='toggle_game_watched')
@login_required
def toggle_game_watched(game_id):
    """Toggle the current user's explicit watched mark for a game."""
    current_user = get_current_user()
    existing = GameWatched.query.filter_by(user_id=current_user.id, game_id=game_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'watched': False, 'game_id': game_id})
    else:
        record = GameWatched(user_id=current_user.id, game_id=game_id)
        db.session.add(record)
        db.session.commit()
        return jsonify({'watched': True, 'game_id': game_id})


@app.route('/film/api/user/<username>/watched-games', endpoint='get_user_watched_games')
@admin_required
def get_user_watched_games(username):
    """Admin endpoint: return all games explicitly marked watched by a user."""
    target_user = User.query.filter_by(username=username).first_or_404()
    rows = (
        db.session.query(
            GameWatched.id.label('watched_id'),
            GameWatched.watched_at,
            Game.id.label('game_id'),
            Game.title,
            Game.opponent,
            Game.game_date,
        )
        .join(Game, GameWatched.game_id == Game.id)
        .filter(GameWatched.user_id == target_user.id)
        .order_by(GameWatched.watched_at.desc())
        .all()
    )
    return jsonify({
        'username': username,
        'watched_games': [
            {
                'game_id': r.game_id,
                'title': r.title,
                'opponent': r.opponent,
                'game_date': r.game_date,
                'watched_at_iso': r.watched_at.isoformat() + 'Z' if r.watched_at else '',
            }
            for r in rows
        ]
    })
