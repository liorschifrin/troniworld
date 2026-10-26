"""Data the game page needs for its player sheet and point-detail option lists."""
from sqlalchemy.orm import selectinload

from . import db
from .models import Game, Point
from .visibility import visible_games_query


def point_field_options(user):
    """Distinct pull/defense/offense labels, from games ``user`` may view only.

    Labels used only in hidden games must not be revealed, and points hidden by a
    CSV reimport do not count.
    """
    rows = (db.session.query(Point.pull_play, Point.defense_type, Point.offense_faced)
            .filter(Point.game_id.in_(visible_games_query(user).with_entities(Game.id)),
                    Point.hidden_by_import.is_(False)).all())
    return {
        'pull_play': sorted({r.pull_play for r in rows if r.pull_play}),
        'defense_type': sorted({r.defense_type for r in rows if r.defense_type}),
        'offense_faced': sorted({r.offense_faced for r in rows if r.offense_faced}),
    }


def game_points(game):
    """The game's visible points in index order, with their players loaded."""
    return game.visible_points.options(selectinload(Point.players)).order_by(Point.point_index).all()


def player_order(game, points):
    """(player names in sheet order, separator index) for a game with points."""
    data = game.player_order_data
    if data and 'players' in data:
        return data['players'], data.get('separator_index')
    if game.roster:
        return [p.name for p in game.roster], None
    names = []
    seen = set()
    for point in points:
        for player in point.players:
            if player.name not in seen:
                names.append(player.name)
                seen.add(player.name)
    return names, None


def build_player_sheet(game, points):
    """The player sheet context, or None when the game has no points or no players."""
    if not points:
        return None
    all_players, separator_index = player_order(game, points)
    # After a "clear" deletion there are no players and the page offers Upload CSV.
    if not all_players:
        return None

    position = {}
    for i, name in enumerate(all_players):
        position.setdefault(name, i)  # the first listing wins, as with list.index
    sheet = {
        'points': points,
        'players': all_players,
        'separator_index': separator_index,
        'point_players': {},  # point_index -> [player names]
        'point_injury_subs': {},
        'point_players_js': {},
    }
    for point in points:
        names = sorted((p.name for p in point.players),
                       key=lambda n: position.get(n, len(all_players)))
        subs = point.injury_subs or {}
        sub_off, sub_on = set(subs.get('off', [])), set(subs.get('on', []))
        sheet['point_players'][point.point_index] = names
        sheet['point_injury_subs'][point.point_index] = subs
        sheet['point_players_js'][point.point_index] = [
            {'name': n, 'sub': 'off' if n in sub_off else ('on' if n in sub_on else None)}
            for n in names
        ]
    return sheet
