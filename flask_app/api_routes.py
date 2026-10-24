import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request

from . import db
from .models import Comment, Game, Point, User, VideoWatchSession
from .utils import admin_required, get_current_user, login_required
from .visibility import can_view_comment, get_visible_game_or_404, visible_games_query

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

_EST = ZoneInfo("America/New_York")


def _fmt_est(dt):
    if dt is None:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(_EST).strftime("%b %d, %Y %I:%M %p")


def _fmt_iso_utc(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def _optional_int(value):
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _comment_type_single(_value):
    # Temporary product policy: keep only one comment type in the new React app.
    return "Comment"


def _serialize_point(point: Point) -> dict:
    return {
        "id": point.id,
        "point_index": point.point_index,
        "timestamp_start": point.timestamp_start,
        "tron_o": bool(point.tron_o),
        "tron_point": bool(point.tron_point),
        "pull_play": point.pull_play,
        "defense_type": point.defense_type,
        "offense_faced": point.offense_faced,
        "players": sorted([p.name for p in point.players]),
    }


def _is_leadership(author_name: str) -> bool:
    user = User.query.filter_by(username=author_name).first()
    return bool(user and user.is_leadership)


def _serialize_reply(reply: Comment) -> dict:
    return {
        "id": reply.id,
        "author_name": reply.author_name,
        "is_leadership": _is_leadership(reply.author_name),
        "comment_type": _comment_type_single(reply.comment_type),
        "timestamp": reply.timestamp,
        "content": reply.content,
        "parent_id": reply.parent_id,
        "created_at": _fmt_est(reply.created_at),
        "created_at_iso": _fmt_iso_utc(reply.created_at),
    }


def _serialize_comment(comment: Comment, viewer: User) -> dict:
    # Callers check the comment itself; replies are filtered here. This API
    # applies the explicit author/recipient baseline with no leadership exception.
    replies = [
        reply
        for reply in Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at.asc()).all()
        if can_view_comment(viewer, reply)
    ]
    return {
        "id": comment.id,
        "author_name": comment.author_name,
        "is_leadership": _is_leadership(comment.author_name),
        "comment_type": _comment_type_single(comment.comment_type),
        "timestamp": comment.timestamp,
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": _fmt_est(comment.created_at),
        "created_at_iso": _fmt_iso_utc(comment.created_at),
        "replies": [_serialize_reply(reply) for reply in replies],
    }


def _serialize_viewer() -> dict:
    user = get_current_user()
    if not user:
        return {
            "username": None,
            "is_admin": False,
            "player_name": None,
        }
    return {
        "username": user.username,
        "is_admin": bool(user.is_admin),
        "player_name": user.player.name if user.player else None,
    }


def _collect_point_field_options(user: User) -> dict:
    visible_points = db.session.query(Point).filter(
        Point.game_id.in_(visible_games_query(user).with_entities(Game.id))
    )
    pull_play = [
        row[0]
        for row in visible_points.with_entities(Point.pull_play)
        .filter(Point.pull_play.isnot(None), Point.pull_play != "")
        .distinct()
        .order_by(Point.pull_play.asc())
        .all()
    ]
    defense_type = [
        row[0]
        for row in visible_points.with_entities(Point.defense_type)
        .filter(Point.defense_type.isnot(None), Point.defense_type != "")
        .distinct()
        .order_by(Point.defense_type.asc())
        .all()
    ]
    offense_faced = [
        row[0]
        for row in visible_points.with_entities(Point.offense_faced)
        .filter(Point.offense_faced.isnot(None), Point.offense_faced != "")
        .distinct()
        .order_by(Point.offense_faced.asc())
        .all()
    ]
    return {
        "pull_play": pull_play,
        "defense_type": defense_type,
        "offense_faced": offense_faced,
    }


def _serialize_game(game: Game, user: User) -> dict:
    points = game.points.order_by(Point.point_index).all()
    comments = Comment.query.filter_by(game_id=game.id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc(),
    ).all()

    viewer = _serialize_viewer()

    if game.player_order_data and "players" in game.player_order_data:
        player_order = game.player_order_data.get("players") or []
        separator_index = game.player_order_data.get("separator_index")
    elif game.roster:
        player_order = sorted([p.name for p in game.roster])
        separator_index = None
    else:
        player_order = []
        separator_index = None

    player_index = {name: idx for idx, name in enumerate(player_order)}
    point_players = {
        str(point.point_index): sorted(
            [player.name for player in point.players],
            key=lambda name: player_index.get(name, len(player_order) + 1),
        )
        for point in points
    }

    usernames = [
        row[0]
        for row in db.session.query(User.username).order_by(User.username.asc()).all()
        if row[0]
    ]
    mentionables = list(dict.fromkeys(usernames + ([game.opponent] if game.opponent else [])))

    return {
        "id": game.id,
        "title": game.title,
        "opponent": game.opponent,
        "youtube_id": game.youtube_id,
        "game_date": game.game_date,
        "final_score_tron": game.final_score_tron,
        "final_score_opponent": game.final_score_opponent,
        "tournament": {
            "id": game.tournament.id,
            "name": game.tournament.name,
            "start_date": game.tournament.start_date,
            "game_number": game.tournament_game_number,
        }
        if game.tournament
        else None,
        "roster": sorted([p.name for p in game.roster]),
        "points": [_serialize_point(point) for point in points],
        "comments": [
            _serialize_comment(comment, user) for comment in comments if can_view_comment(user, comment)
        ],
        "point_field_options": _collect_point_field_options(user),
        "viewer": viewer,
        "mentionables": mentionables,
        "player_sheet": {
            "players": player_order,
            "separator_index": separator_index,
            "point_players": point_players,
        },
    }


@api_v1.route("/games", methods=["GET"])
@login_required
def games_index():
    games = visible_games_query(get_current_user()).order_by(
        Game.game_date.desc().nullslast(), Game.id.desc()
    ).all()
    payload = []
    for game in games:
        payload.append(
            {
                "id": game.id,
                "title": game.title,
                "opponent": game.opponent,
                "youtube_id": game.youtube_id,
                "game_date": game.game_date,
                "final_score_tron": game.final_score_tron,
                "final_score_opponent": game.final_score_opponent,
            }
        )
    return jsonify({"games": payload})


@api_v1.route("/games/<int:game_id>", methods=["GET"])
@login_required
def game_detail(game_id: int):
    current_user = get_current_user()
    game = get_visible_game_or_404(game_id, current_user)
    return jsonify({"game": _serialize_game(game, current_user)})


@api_v1.route("/games/<int:game_id>/comments", methods=["GET"])
@login_required
def game_comments(game_id: int):
    current_user = get_current_user()
    get_visible_game_or_404(game_id, current_user)
    comments = Comment.query.filter_by(game_id=game_id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc(),
    ).all()
    return jsonify({
        "comments": [
            _serialize_comment(comment, current_user)
            for comment in comments
            if can_view_comment(current_user, comment)
        ]
    })


@api_v1.route("/games/<int:game_id>/comments", methods=["POST"])
@login_required
def create_game_comment(game_id: int):
    current_user = get_current_user()
    get_visible_game_or_404(game_id, current_user)
    data = request.get_json(silent=True) or {}

    content = (data.get("content") or "").strip()
    parent_id = _optional_int(data.get("parent_id"))
    timestamp = _optional_int(data.get("timestamp"))
    point_id = _optional_int(data.get("point_id"))

    if not content:
        return jsonify({"error": "Content is required"}), 400

    if parent_id is not None:
        parent = Comment.query.filter_by(id=parent_id, game_id=game_id).first()
        if not parent:
            return jsonify({"error": "Parent comment not found"}), 404

    comment = Comment(
        game_id=game_id,
        parent_id=parent_id,
        point_id=point_id,
        author_name=current_user.username,
        comment_type="Comment",
        timestamp=timestamp,
        content=content,
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify({"success": True, "comment": _serialize_comment(comment, current_user)}), 201


@api_v1.route("/games/<int:game_id>/comments/<int:comment_id>", methods=["PATCH"])
@login_required
def update_game_comment(game_id: int, comment_id: int):
    current_user = get_current_user()
    get_visible_game_or_404(game_id, current_user)
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if comment.author_name != current_user.username:
        return jsonify({"error": "Unauthorized"}), 403

    new_content = (data.get("content") or "").strip()
    if not new_content:
        return jsonify({"error": "Content is required"}), 400

    comment.content = new_content
    comment.comment_type = "Comment"
    db.session.commit()
    return jsonify({"success": True, "comment": _serialize_comment(comment, current_user)})


@api_v1.route("/games/<int:game_id>/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_game_comment(game_id: int, comment_id: int):
    current_user = get_current_user()
    get_visible_game_or_404(game_id, current_user)
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    if not current_user.is_admin and comment.author_name != current_user.username:
        return jsonify({"error": "Unauthorized"}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({"success": True})


@api_v1.route("/games/<int:game_id>/points/<int:point_id>", methods=["PATCH"])
@admin_required
def update_game_point(game_id: int, point_id: int):
    point = Point.query.filter_by(id=point_id, game_id=game_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if "pull_play" in data:
        point.pull_play = (data.get("pull_play") or "").strip() or None
    if "defense_type" in data:
        point.defense_type = (data.get("defense_type") or "").strip() or None
    if "offense_faced" in data:
        point.offense_faced = (data.get("offense_faced") or "").strip() or None
    if "timestamp_start" in data:
        point.timestamp_start = _optional_int(data.get("timestamp_start"))

    db.session.commit()
    return jsonify({"success": True, "point": _serialize_point(point)})


@api_v1.route("/games/<int:game_id>/track-watch-time", methods=["POST"])
@login_required
def track_watch_time(game_id: int):
    current_user = get_current_user()
    get_visible_game_or_404(game_id, current_user)

    data = request.get_json(silent=True)
    if data is None:
        raw = request.get_data(cache=False, as_text=True) or ""
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {}

    seconds_watched = _optional_int(data.get("seconds_watched"))
    if not seconds_watched or seconds_watched <= 0:
        return jsonify({"success": False, "error": "Invalid watch duration"}), 400

    session_id = _optional_int(data.get("session_id"))
    watch_session = None

    if session_id:
        watch_session = VideoWatchSession.query.filter_by(
            id=session_id,
            user_id=current_user.id,
            game_id=game_id,
        ).first()

    if not watch_session:
        watch_session = VideoWatchSession(
            user_id=current_user.id,
            game_id=game_id,
            watch_duration_seconds=seconds_watched,
            session_start=datetime.utcnow(),
            last_updated=datetime.utcnow(),
        )
        db.session.add(watch_session)
    else:
        watch_session.watch_duration_seconds += seconds_watched
        watch_session.last_updated = datetime.utcnow()

    db.session.commit()

    return jsonify(
        {
            "success": True,
            "session_id": watch_session.id,
            "total_watched": watch_session.watch_duration_seconds,
        }
    )
