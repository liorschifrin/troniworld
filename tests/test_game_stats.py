"""T11: the shared point tallies behind the team data and My Games pages."""
from types import SimpleNamespace

from flask_app import game_stats
from flask_app.models import Game, Player, Point


def pt(o, scored):
    return SimpleNamespace(tron_o=o, tron_point=scored)


def test_tally_and_rate():
    counts = game_stats.tally([pt(True, True), pt(True, False), pt(False, True), pt(None, False)])
    assert counts == {'o_count': 2, 'o_scored': 1, 'd_count': 2, 'd_scored': 1}
    assert game_stats.rate(1, 2) == 50.0
    assert game_stats.rate(0, 0) is None and game_stats.rate(0, 0, 0) == 0
    assert game_stats.tally([]) == {'o_count': 0, 'o_scored': 0, 'd_count': 0, 'd_scored': 0}


def test_loaders_skip_hidden_points_and_count_roster_not_points(db):
    first, second = Game(title='G1', opponent='X'), Game(title='G2', opponent='X')
    played, benched = Player(name='Played'), Player(name='Benched')
    db.session.add_all([first, second, played, benched])
    db.session.flush()
    visible = Point(game_id=first.id, point_index=1, tron_o=True)
    hidden = Point(game_id=first.id, point_index=2, hidden_by_import=True)
    other = Point(game_id=second.id, point_index=1)
    visible.players = [played]
    hidden.players = [played]
    first.roster = [played, benched]
    second.roster = [played]
    db.session.add_all([visible, hidden, other])
    db.session.commit()

    loaded = game_stats.visible_points({first.id, second.id}, with_players=True)
    assert [p.id for p in loaded] == [visible.id, other.id]
    assert game_stats.group_by_game(loaded)[first.id] == [visible]
    assert game_stats.points_of_player(played.id, [first.id, second.id]) == {first.id: [visible]}
    assert game_stats.games_played({first.id, second.id}) == {played.id: 2, benched.id: 1}
    assert game_stats.games_played({first.id}) == {played.id: 1, benched.id: 1}
    assert game_stats.visible_points([]) == [] and game_stats.games_played([]) == {}
