"""Point tallies shared by the team data page and the My Games page.

Both pages used to run one query per game (and one per point for its players).
These helpers load the points of many games at once. Hidden-by-import points are
always excluded (see ``Game.visible_points``); do not read ``game.points`` here.
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import db
from .models import Point, game_roster, point_players


def rate(scored, count, empty=None):
    """Percentage scored, or ``empty`` when there were no points."""
    return scored / count * 100 if count > 0 else empty


def tally(points):
    """Offense/defense counts for a list of points."""
    o_points = [p for p in points if p.tron_o]
    d_points = [p for p in points if not p.tron_o]
    return {
        'o_count': len(o_points), 'o_scored': sum(1 for p in o_points if p.tron_point),
        'd_count': len(d_points), 'd_scored': sum(1 for p in d_points if p.tron_point),
    }


def visible_points(game_ids, with_players=False):
    """Visible points of the given games, in id order, with players loaded in one extra query."""
    query = Point.query.filter(Point.game_id.in_(list(game_ids)), Point.hidden_by_import.is_(False))
    if with_players:
        query = query.options(selectinload(Point.players))
    return query.order_by(Point.id).all()


def group_by_game(points):
    grouped = {}
    for point in points:
        grouped.setdefault(point.game_id, []).append(point)
    return grouped


def points_of_player(player_id, game_ids):
    """Visible points of the given games that include one player, grouped by game id."""
    rows = (Point.query
            .join(point_players, point_players.c.point_id == Point.id)
            .filter(point_players.c.player_id == player_id,
                    Point.game_id.in_(list(game_ids)), Point.hidden_by_import.is_(False))
            .order_by(Point.id).all())
    return group_by_game(rows)


def games_played(game_ids):
    """Number of the given games each player is on the roster of: {player_id: count}."""
    counts = {}
    rows = db.session.execute(select(game_roster.c.player_id).where(game_roster.c.game_id.in_(list(game_ids))))
    for (player_id,) in rows:
        counts[player_id] = counts.get(player_id, 0) + 1
    return counts
