from datetime import timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request

from . import db
from .models import Comment, Game, Point
from .utils import admin_required, get_current_user, login_required

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

_EST = ZoneInfo("America/New_York")
_VALID_COMMENT_TYPES = {"Comment", "Question", "Highlight", "Event"}


def _fmt_est(dt):
    if dt is None:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(_EST).strftime("%b %d, %Y %I:%M %p")


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


def _serialize_reply(reply: Comment) -> dict:
    return {
        "id": reply.id,
        "author_name": reply.author_name,
        "comment_type": reply.comment_type,
        "timestamp": reply.timestamp,
        "content": reply.content,
        "parent_id": reply.parent_id,
        "created_at": _fmt_est(reply.created_at),
    }


def _serialize_comment(comment: Comment) -> dict:
    replies = Comment.query.filter_by(parent_id=comment.id).order_by(Comment.created_at.asc()).all()
    return {
        "id": comment.id,
        "author_name": comment.author_name,
        "comment_type": comment.comment_type,
        "timestamp": comment.timestamp,
        "content": comment.content,
        "parent_id": comment.parent_id,
        "created_at": _fmt_est(comment.created_at),
        "replies": [_serialize_reply(reply) for reply in replies],
    }


def _serialize_game(game: Game) -> dict:
    points = game.points.order_by(Point.point_index).all()
    comments = Comment.query.filter_by(game_id=game.id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc(),
    ).all()
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
        "comments": [_serialize_comment(comment) for comment in comments],
    }


@api_v1.route("/games", methods=["GET"])
@login_required
def games_index():
    games = Game.query.order_by(Game.game_date.desc().nullslast(), Game.id.desc()).all()
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
    game = Game.query.get_or_404(game_id)
    return jsonify({"game": _serialize_game(game)})


@api_v1.route("/games/<int:game_id>/comments", methods=["GET"])
@login_required
def game_comments(game_id: int):
    Game.query.get_or_404(game_id)
    comments = Comment.query.filter_by(game_id=game_id, parent_id=None).order_by(
        Comment.timestamp.asc().nullslast(),
        Comment.created_at.asc(),
    ).all()
    return jsonify({"comments": [_serialize_comment(comment) for comment in comments]})


@api_v1.route("/games/<int:game_id>/comments", methods=["POST"])
@login_required
def create_game_comment(game_id: int):
    Game.query.get_or_404(game_id)
    current_user = get_current_user()
    data = request.get_json(silent=True) or {}

    content = (data.get("content") or "").strip()
    comment_type = (data.get("comment_type") or "Comment").strip()
    parent_id = data.get("parent_id")
    timestamp = data.get("timestamp")
    point_id = data.get("point_id")

    if comment_type not in _VALID_COMMENT_TYPES:
        comment_type = "Comment"

    if comment_type != "Event" and not content:
        return jsonify({"error": "Content is required"}), 400

    comment = Comment(
        game_id=game_id,
        parent_id=parent_id,
        point_id=point_id,
        author_name=current_user.username,
        comment_type=comment_type,
        timestamp=timestamp,
        content=content,
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify({"success": True, "comment": _serialize_comment(comment)}), 201


@api_v1.route("/games/<int:game_id>/comments/<int:comment_id>", methods=["PATCH"])
@login_required
def update_game_comment(game_id: int, comment_id: int):
    current_user = get_current_user()
    comment = Comment.query.filter_by(id=comment_id, game_id=game_id).first_or_404()
    data = request.get_json(silent=True) or {}

    if comment.author_name != current_user.username:
        return jsonify({"error": "Unauthorized"}), 403

    new_content = (data.get("content") or "").strip()
    new_comment_type = (data.get("comment_type") or comment.comment_type).strip()

    if new_comment_type not in _VALID_COMMENT_TYPES:
        return jsonify({"error": "Invalid comment type"}), 400
    if new_comment_type != "Event" and not new_content:
        return jsonify({"error": "Content is required"}), 400

    comment.content = new_content
    comment.comment_type = new_comment_type
    db.session.commit()
    return jsonify({"success": True, "comment": _serialize_comment(comment)})


@api_v1.route("/games/<int:game_id>/comments/<int:comment_id>", methods=["DELETE"])
@login_required
def delete_game_comment(game_id: int, comment_id: int):
    current_user = get_current_user()
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
        point.pull_play = data["pull_play"]
    if "defense_type" in data:
        point.defense_type = data["defense_type"]
    if "offense_faced" in data:
        point.offense_faced = data["offense_faced"]
    if "timestamp_start" in data:
        point.timestamp_start = data["timestamp_start"]

    db.session.commit()
    return jsonify({"success": True, "point": _serialize_point(point)})
