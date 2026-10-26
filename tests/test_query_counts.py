"""T11 query-count evidence: how many SQL statements representative pages issue.

Statements are counted with a SQLAlchemy ``before_cursor_execute`` listener on the
test engine, for one request after the session cache is cleared. ``BEFORE`` holds
the counts measured at the T10 head (``5ff100f``) and never changes. ``CEILING``
holds the counts at the current head; a change that makes a page issue more
statements fails here. Each size builds a synthetic dataset; the large one shows
whether the count grows with the data.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import event

SIZES = {'small': dict(games=2, points=4, replies=2), 'large': dict(games=6, points=12, replies=5)}

# scenario -> {size: statements}. Measured with: python -m pytest tests/test_query_counts.py -s -k report
BEFORE = {
    'game_page': {'small': 10, 'large': 18},
    'comments_api': {'small': 11, 'large': 23},
    'games_list': {'small': 3, 'large': 3},
    'team_data': {'small': 23, 'large': 27},
    'my_games': {'small': 14, 'large': 82},
}
CEILING = {name: dict(sizes) for name, sizes in BEFORE.items()}
CEILING['comments_api'] = {'small': 5, 'large': 5}  # serializers + batched replies/authors

PATHS = {
    'game_page': '/film/games/{first}',
    'comments_api': '/film/api/games/{first}/comments',
    'games_list': '/film/games',
    'team_data': '/film/data',
    'my_games': '/film/my-games',
}


@pytest.fixture
def dataset(db, records):
    """Games in tournaments with players, points, top-level comments and replies."""
    from flask_app.models import Comment, Game, Player, Point, Tournament, User

    def build(games, points, replies):
        names = [f'Synthetic Player {i}' for i in range(8)]
        players = [Player(name=n, active=True) for n in names]
        db.session.add_all(players)
        commenters = [User(username=f'commenter{i}', hashed_password='x', is_leadership=i % 2 == 0)
                      for i in range(4)]
        db.session.add_all(commenters)
        records['users']['ordinary'].player = players[0]
        tournaments = [Tournament(name=f'Synthetic Cup {i}', start_date=f'2026-0{i + 1}-01') for i in range(2)]
        db.session.add_all(tournaments)
        db.session.flush()
        created = []
        for g in range(games):
            game = Game(title=f'Synthetic game {g}', opponent=f'Visitors {g}',
                        game_date=f'2026-0{(g % 8) + 1}-1{g % 9}', tournament_id=tournaments[g % 2].id,
                        tournament_game_number=g, youtube_id='aaaaaaaaaaa',
                        final_score_tron=10 + g, final_score_opponent=9,
                        player_order_data={'players': names, 'separator_index': 4})
            game.roster = list(players)
            db.session.add(game)
            db.session.flush()
            created.append(game)
            for i in range(1, points + 1):
                point = Point(game_id=game.id, point_index=i, timestamp_start=i * 30, tron_o=i % 2 == 0,
                              tron_point=i % 3 != 0, pull_play=f'pull{i % 3}', defense_type=f'def{i % 2}',
                              offense_faced=f'off{i % 4}')
                point.players = players[i % 3: i % 3 + 5]
                db.session.add(point)
            for c in range(replies):
                top = Comment(game_id=game.id, author_name=commenters[c % 4].username, content=f'top {c}',
                              comment_type='Comment', timestamp=c * 20)
                db.session.add(top)
                db.session.flush()
                for r in range(2):
                    db.session.add(Comment(game_id=game.id, parent_id=top.id,
                                           author_name=commenters[(c + r + 1) % 4].username,
                                           content=f'reply {c}.{r}', comment_type='Comment'))
        db.session.commit()
        return created

    return build


@contextmanager
def counting(db):
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        yield statements
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)


def measure(db, client, path):
    db.session.expire_all()
    db.session.remove()
    with counting(db) as statements:
        response = client.get(path)
    assert response.status_code == 200, path
    return len(statements)


@pytest.mark.parametrize('size', list(SIZES))
@pytest.mark.parametrize('scenario', list(PATHS))
def test_query_count_is_not_higher_than_recorded(db, dataset, ordinary, scenario, size):
    games = dataset(**SIZES[size])
    count = measure(db, ordinary, PATHS[scenario].format(first=games[0].id))
    print(f'QUERYCOUNT {scenario} {size} {count}')
    before, ceiling = BEFORE[scenario][size], CEILING[scenario][size]
    if ceiling is None:
        pytest.skip('baseline not recorded yet')
    assert count <= ceiling, f'{scenario}/{size}: {count} statements, recorded ceiling {ceiling}'
    assert count <= before
