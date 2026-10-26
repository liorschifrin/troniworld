"""T11: player sheet and option-list builders extracted from the game page route."""
from flask_app import player_sheet
from flask_app.models import Game, Player, Point


def make_game(db, order=None, roster=(), **kw):
    game = Game(title='G', opponent='X', player_order_data=order, **kw)
    db.session.add(game)
    db.session.flush()
    game.roster = list(roster)
    return game


def add_point(db, game, index, players, subs=None, hidden=False):
    point = Point(game_id=game.id, point_index=index, injury_subs=subs, hidden_by_import=hidden)
    point.players = players
    db.session.add(point)
    db.session.flush()
    return point


def players(db, *names):
    rows = [Player(name=n) for n in names]
    db.session.add_all(rows)
    db.session.flush()
    return rows


def test_no_points_or_no_players_gives_no_sheet(db):
    game = make_game(db)
    assert player_sheet.build_player_sheet(game, []) is None
    add_point(db, game, 1, [])
    assert player_sheet.build_player_sheet(game, player_sheet.game_points(game)) is None


def test_stored_order_wins_and_unknown_names_sort_last(db):
    a, b, c = players(db, 'A', 'B', 'C')
    game = make_game(db, order={'players': ['C', 'A', 'B', 'A'], 'separator_index': 2}, roster=[a])
    add_point(db, game, 1, [a, b, c], subs={'off': ['B'], 'on': ['A']})
    sheet = player_sheet.build_player_sheet(game, player_sheet.game_points(game))
    assert sheet['players'] == ['C', 'A', 'B', 'A'] and sheet['separator_index'] == 2
    assert sheet['point_players'] == {1: ['C', 'A', 'B']}
    assert sheet['point_players_js'][1] == [{'name': 'C', 'sub': None}, {'name': 'A', 'sub': 'on'},
                                            {'name': 'B', 'sub': 'off'}]
    assert sheet['point_injury_subs'][1] == {'off': ['B'], 'on': ['A']}


def test_fallbacks_are_roster_then_points_in_order_of_appearance(db):
    a, b = players(db, 'A', 'B')
    roster_game = make_game(db, roster=[b, a])
    add_point(db, roster_game, 1, [a])
    assert player_sheet.build_player_sheet(roster_game, player_sheet.game_points(roster_game))['players'] == ['B', 'A']
    bare = make_game(db)
    add_point(db, bare, 1, [b])
    add_point(db, bare, 2, [a, b])
    sheet = player_sheet.build_player_sheet(bare, player_sheet.game_points(bare))
    assert sheet['players'] == ['B', 'A'] and sheet['separator_index'] is None
    assert sheet['point_injury_subs'] == {1: {}, 2: {}}


def test_hidden_points_are_not_on_the_sheet(db):
    (a,) = players(db, 'A')
    game = make_game(db, roster=[a])
    add_point(db, game, 1, [a])
    add_point(db, game, 2, [a], hidden=True)
    assert [p.point_index for p in player_sheet.game_points(game)] == [1]


def test_option_lists_come_only_from_visible_games_and_points(db, records):
    shown = records['game']
    for index, labels in ((2, ('pull b', 'zone', 'vert')), (3, ('pull a', None, None))):
        db.session.add(Point(game_id=shown.id, point_index=index, pull_play=labels[0],
                             defense_type=labels[1], offense_faced=labels[2]))
    db.session.add(Point(game_id=shown.id, point_index=4, pull_play='retired', hidden_by_import=True))
    db.session.add(Point(game_id=records['hidden'].id, point_index=1, pull_play='secret',
                         defense_type='secret D', offense_faced='secret O'))
    db.session.commit()
    ordinary = records['users']['ordinary']
    admin = records['users']['admin']
    assert player_sheet.point_field_options(ordinary) == {
        'pull_play': ['pull a', 'pull b'], 'defense_type': ['zone'], 'offense_faced': ['vert']}
    assert 'secret' in player_sheet.point_field_options(admin)['pull_play']
