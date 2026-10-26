"""T10: CSV validation, import preview, atomic apply (synthetic data only)."""
import re

import pytest
from sqlalchemy import select

from flask_app import csv_import
from flask_app.csv_import import parse_game_csv

# Points 1-4 (columns B-E). Section break after Alice and Bob.
BASE = (
    ',O,X,O,X\n'
    ',1,,3,\n'
    ',,2,,4\n'
    '\n'
    'Alice,1,,1,2\n'
    'Bob,2,1,,\n'
    '\n'
    'Cara,,2,2,3\n'
    'END PLAYERS\n'
    'ignored,notes,after the marker\n'
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def snapshot(db):
    """Every value in every table, so 'nothing written' means nothing at all."""
    db.session.expire_all()
    return {t.name: [tuple(r) for r in db.session.execute(select(t).order_by(*t.primary_key.columns))]
            for t in db.metadata.sorted_tables}


@pytest.fixture
def game(db):
    from flask_app.models import Game
    g = Game(title='Import game', opponent='Synthetic visitors')
    db.session.add(g)
    db.session.commit()
    return g


def url(game, tail='upload_csv'):
    return f'/film/games/{game.id}/{tail}'


def upload(client, game, text, name='sheet.csv'):
    from io import BytesIO
    raw = text if isinstance(text, bytes) else text.encode()
    return client.post(url(game), data={'csv_file': (BytesIO(raw), name)}, content_type='multipart/form-data')


def token_of(html):
    return re.search(r'name="state_token" value="([0-9a-f]+)"', html).group(1)


def csv_of(html):
    import html as htmllib
    return htmllib.unescape(re.search(r'name="csv_text" value="([^"]*)"', html, re.S).group(1))


def preview(client, game, text):
    response = upload(client, game, text)
    assert response.status_code == 200, response.get_data(as_text=True)[:600]
    html = response.get_data(as_text=True)
    return html, token_of(html), csv_of(html)


def apply(client, game, text, token, confirm=True):
    data = {'csv_text': text, 'state_token': token}
    if confirm:
        data['confirm_hidden'] = '1'
    return client.post(url(game, 'upload_csv/apply'), data=data)


def do_import(client, game, text, confirm=True):
    _, token, csv_text = preview(client, game, text)
    response = apply(client, game, csv_text, token, confirm)
    assert response.status_code == 302, response.get_data(as_text=True)[:600]
    return response


def points_of(game_id):
    from flask_app.models import Point
    return {p.point_index: p for p in Point.query.filter_by(game_id=game_id).all()}


def names(point):
    return sorted(p.name for p in point.players)


# ---------------------------------------------------------------------------
# parser (pure)
# ---------------------------------------------------------------------------

def test_parse_valid_sheet():
    sheet, errors = parse_game_csv(BASE)
    assert errors == []
    assert [(p.index, p.tron_o, p.tron_point) for p in sheet.points] == [
        (1, True, True), (2, False, False), (3, True, True), (4, False, False)]
    assert [p.players for p in sheet.points] == [
        ('Alice', 'Bob'), ('Bob', 'Cara'), ('Alice', 'Cara'), ('Alice', 'Cara')]
    # Section order: Alice, Bob, then Cara after the first blank row; rows after END PLAYERS are ignored.
    assert sheet.player_order_data == {'players': ['Alice', 'Bob', 'Cara'], 'separator_index': 2}


def test_section_order_without_a_break_or_end_marker():
    sheet, errors = parse_game_csv(',O\n,1\n,\n\nAlice,1\nBob,1\n')
    assert errors == [] and sheet.player_order_data == {'players': ['Alice', 'Bob'], 'separator_index': None}
    # No blank spacer row after row 3 is accepted too.
    sheet, errors = parse_game_csv(',O\n,1\n,\nAlice,1\n\nBob,1\n')
    assert errors == [] and sheet.player_order_data == {'players': ['Alice', 'Bob'], 'separator_index': 1}


def test_injury_notation_off_has_trailing_slash_on_has_leading_slash():
    sheet, errors = parse_game_csv(',O,X\n,1,\n,,2\n\nAlice,3/,1\nBob,/2,\nCara,4,5\n')
    assert errors == []
    first, second = sheet.points
    assert first.players == ('Alice', 'Bob', 'Cara')  # a substituted player also played the point
    assert first.sub_off == ('Alice',) and first.sub_on == ('Bob',)
    assert first.injury_subs == {'off': ['Alice'], 'on': ['Bob']}
    assert second.injury_subs is None


@pytest.mark.parametrize('cell', ['/', '//', '3/4', '/3/', '3//', '//3', ' / '])
def test_malformed_injury_notation_is_an_error_with_a_location(cell):
    sheet, errors = parse_game_csv(f',O\n,1\n,\n\nAlice,{cell}\n')
    assert sheet is None
    assert [(e.row, e.column) for e in errors] == [(5, 'B')]
    assert 'injury notation' in errors[0].message


@pytest.mark.parametrize('text,where,fragment', [
    (',Q\n,1\n,\n\nAlice,1\n', (1, 'B'), 'Invalid O/D'),
    (',o,\n,1,1\n,,\n\nAlice,1,1\n', (1, 'C'), 'Missing O/D'),
    (',O\n,1\n,2\n\nAlice,1\n', (2, 'B'), 'only one team'),
    (',O\n,\n,\n\nAlice,1\n', (2, 'B'), 'Neither'),
    (',O,,O\n,1,,1\n,,,\n\nAlice,1,,1\n', (1, 'C'), 'empty between'),
    (',O\n,1\n,\n\nAlice,1,1\n', (1, 'C'), 'Missing O/D'),               # player mark past the header
    (',O\n,1\n,\n\n,1\n', (5, 'A'), 'no player name'),
    (',O\n,1\n,\n\nAlice,1\nAlice,1\n', (6, 'A'), 'already listed on row 5'),
    (',O\n,1\n,\n\n' + 'N' * 101 + ',1\n', (5, 'A'), 'longer than 100'),
])
def test_invalid_columns_and_rows_are_reported_not_skipped(text, where, fragment):
    sheet, errors = parse_game_csv(text)
    assert sheet is None
    assert (errors[0].row, errors[0].column) == where, errors
    assert fragment in errors[0].message


def test_file_level_errors():
    for raw, fragment in [(b'\xff\xfe\x00bad', 'UTF-8'), (',O\n,1\n', 'at least 4 rows'),
                          (b'x' * (csv_import.MAX_CSV_BYTES + 1), 'larger than'),
                          (',\n,\n,\n\nAlice,\n', 'no points'),
                          ('\n'.join([',O'] * 1001), 'rows'),
                          ('A,' * 501 + '\n\n\n\n', 'columns')]:
        sheet, errors = parse_game_csv(raw)
        assert sheet is None and fragment in errors[0].message, (raw[:20], errors)
        assert errors[0].location == 'File'


def test_bom_crlf_blank_padding_and_case_are_accepted():
    text = '﻿,o,,,\r\n,1,,,\r\n,,,,\r\n\r\nAlice,1,,,\r\nEND PLAYERS\r\n'
    sheet, errors = parse_game_csv(text.encode('utf-8'))
    assert errors == [] and [p.index for p in sheet.points] == [1]


def test_every_problem_is_listed_not_just_the_first():
    _, errors = parse_game_csv(',Q,Z\n,1,1\n,,\n\nAlice,1/2,1\n')
    assert {(e.row, e.column) for e in errors} == {(1, 'B'), (1, 'C'), (5, 'B')}


# ---------------------------------------------------------------------------
# invalid CSV writes nothing
# ---------------------------------------------------------------------------

INVALID = {
    'bad od': ',Q\n,1\n,\n\nAlice,1\n',
    'missing od': ',O,\n,1,1\n,,\n\nAlice,1,1\n',
    'both scores': ',O\n,1\n,2\n\nAlice,1\n',
    'no score': ',O\n,\n,\n\nAlice,1\n',
    'interior blank column': ',O,,O\n,1,,1\n,,,\n\nAlice,1,,1\n',
    'bad injury notation': ',O\n,1\n,\n\nAlice,3/4\n',
    'duplicate player': ',O\n,1\n,\n\nAlice,1\nAlice,1\n',
    'nameless row': ',O\n,1\n,\n\n,1\n',
    'too short': ',O\n,1\n',
    'no points': ',\n,\n,\n\nAlice,\n',
    'not utf8': b'\xff\xfe,O\n',
}


@pytest.mark.parametrize('case', sorted(INVALID))
def test_invalid_csv_leaves_data_unchanged_on_preview_and_apply(admin, db, game, case):
    # Existing game data the import must not touch.
    run_import = lambda text: do_import(admin, game, text)
    run_import(BASE)
    before = snapshot(db)
    response = upload(admin, game, INVALID[case])
    assert response.status_code == 400
    assert b'nothing was changed' in response.data
    assert snapshot(db) == before
    # The apply step re-validates its own input, so a forged body cannot bypass the parser either.
    text = INVALID[case] if isinstance(INVALID[case], str) else 'garbage'
    response = apply(admin, game, text, 'f' * 64)
    assert response.status_code == 400
    assert snapshot(db) == before


def test_invalid_csv_on_an_empty_game_creates_no_players_or_accounts(admin, db, game):
    before = snapshot(db)
    assert upload(admin, game, INVALID['bad od']).status_code == 400
    assert upload(admin, game, INVALID['bad injury notation']).status_code == 400
    assert snapshot(db) == before


def test_error_page_lists_row_and_column_and_caps_the_list(admin, db, game):
    wide = ',' + ','.join(['Q'] * 150) + '\n,' + ','.join(['1'] * 150) + '\n\n\nAlice,1\n'
    response = upload(admin, game, wide)
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    assert '150 problems found' in html and 'Showing the first 100' in html
    assert 'Row 1, column B' in html and 'Invalid O/D value' in html


def test_non_csv_name_missing_file_and_empty_name_are_rejected(admin, db, game):
    before = snapshot(db)
    assert upload(admin, game, BASE, name='sheet.txt').status_code == 400
    assert admin.post(url(game), data={}).status_code == 400
    from io import BytesIO
    assert admin.post(url(game), data={'csv_file': (BytesIO(b''), '')},
                      content_type='multipart/form-data').status_code == 400
    assert snapshot(db) == before


# ---------------------------------------------------------------------------
# preview
# ---------------------------------------------------------------------------

def test_preview_of_a_first_import_lists_additions_and_writes_nothing(admin, db, game):
    before = snapshot(db)
    html, token, _ = preview(admin, game, BASE)
    assert snapshot(db) == before  # a preview never writes, not even the new players
    assert '<b>4</b> added' in html and '<b>0</b> changed' in html and '<b>0</b> hidden by reimport' in html
    assert 'section-added' in html and 'section-hidden' not in html
    assert 'New players created' in html and 'Alice, Bob, Cara' in html
    assert 'Player sheet order' in html and 'section break after 2' in html
    assert re.fullmatch(r'[0-9a-f]{64}', token)


def test_preview_lists_additions_changes_and_hidden_points(admin, db, game):
    do_import(admin, game, BASE)
    changed = ',O,O,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\nEND PLAYERS\n'
    html, _, _ = preview(admin, game, changed)
    assert '<b>0</b> added' in html and '<b>2</b> changed' in html and '<b>1</b> unchanged' in html
    assert 'id="section-changed"' in html
    assert 'Offense/defense: Defense → Offense' in html            # point 2
    assert 'Players: -Cara' in html                                  # Cara dropped from points 2 and 3
    assert 'id="section-hidden"' in html and '<b>1</b> hidden by reimport' in html and '<td>4</td>' in html
    assert 'Removed from roster: Cara' in html
    assert 'Alice, Bob, Cara (section break after 2) → Alice, Bob' in html

    added = BASE.replace(',O,X,O,X', ',O,X,O,X,O').replace(',1,,3,', ',1,,3,,5').replace(
        'Alice,1,,1,2', 'Alice,1,,1,2,3')
    html, _, _ = preview(admin, game, added)
    assert '<b>1</b> added' in html and 'id="section-added"' in html and '<b>4</b> unchanged' in html
    assert 'Players: Alice' in html


def test_preview_of_an_identical_reimport_changes_nothing(admin, db, game):
    do_import(admin, game, BASE)
    html, _, _ = preview(admin, game, BASE)
    assert '<b>0</b> added' in html and '<b>0</b> changed' in html and '<b>4</b> unchanged' in html
    assert 'Applying it changes nothing' in html


def test_preview_escapes_csv_content(admin, db, game):
    evil = ',O\n,1\n,\n\n<script>alert(1)</script>,1\n'
    html, _, text = preview(admin, game, evil)
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert text == evil  # round-trips through the hidden field


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

def test_first_import_creates_points_players_roster_and_sheet_order(admin, db, game):
    do_import(admin, game, BASE)
    pts = points_of(game.id)
    assert sorted(pts) == [1, 2, 3, 4] and not any(p.hidden_by_import for p in pts.values())
    assert names(pts[1]) == ['Alice', 'Bob'] and names(pts[2]) == ['Bob', 'Cara']
    assert (pts[1].tron_o, pts[1].tron_point, pts[2].tron_o, pts[2].tron_point) == (True, True, False, False)
    assert sorted(p.name for p in game.roster) == ['Alice', 'Bob', 'Cara']
    assert game.player_order_data == {'players': ['Alice', 'Bob', 'Cara'], 'separator_index': 2}


def test_injury_notation_round_trips_to_the_player_sheet(admin, db, game):
    do_import(admin, game, ',O,X\n,1,\n,,2\n\nAlice,3/,1\nBob,/2,\nCara,4,5\n')
    p1, p2 = points_of(game.id)[1], points_of(game.id)[2]
    assert p1.injury_subs == {'off': ['Alice'], 'on': ['Bob']} and p2.injury_subs is None
    assert names(p1) == ['Alice', 'Bob', 'Cara']
    html = admin.get(f'/film/games/{game.id}').get_data(as_text=True)
    assert 'data-sub-status="off"' in html and 'data-sub-status="on"' in html


def test_reimport_preserves_annotations_on_retained_points(admin, db, game):
    from flask_app.models import Comment
    do_import(admin, game, ',O,X\n,1,\n,,2\n\nAlice,3/,1\nBob,/2,\nCara,4,5\n')
    p1 = points_of(game.id)[1]
    p1.timestamp_start, p1.pull_play, p1.defense_type, p1.offense_faced = 125, 'Flick', 'Zone', 'Vertical'
    p2 = points_of(game.id)[2]
    p2.not_filmed = True
    db.session.add(Comment(game_id=game.id, point_id=p1.id, author_name='admin', content='tagged',
                           comment_type='Comment', timestamp=130))
    db.session.commit()
    ids = {i: p.id for i, p in points_of(game.id).items()}
    before = snapshot(db)

    html, _, _ = preview(admin, game, ',O,X\n,1,\n,,2\n\nAlice,3/,1\nBob,/2,\nCara,4,5\n')
    assert 'Applying it changes nothing' in html
    do_import(admin, game, ',O,X\n,1,\n,,2\n\nAlice,3/,1\nBob,/2,\nCara,4,5\n')
    assert snapshot(db) == before  # byte-for-byte: same ids, same links, same annotations

    # A real change on point 1 (Cara swaps in for Bob, no more injury sub) keeps everything else.
    do_import(admin, game, ',O,X\n,1,\n,,2\n\nAlice,3,1\nBob,,\nCara,4,5\n')
    pts = points_of(game.id)
    assert {i: p.id for i, p in pts.items()} == ids
    assert names(pts[1]) == ['Alice', 'Cara'] and pts[1].injury_subs is None
    assert (pts[1].timestamp_start, pts[1].pull_play, pts[1].defense_type, pts[1].offense_faced) == (
        125, 'Flick', 'Zone', 'Vertical')
    assert pts[2].not_filmed is True
    comment = Comment.query.filter_by(content='tagged').one()
    assert comment.point_id == ids[1] and comment.content == 'tagged' and comment.timestamp == 130


def test_points_missing_from_the_csv_are_hidden_not_deleted(admin, db, game):
    from flask_app.models import Comment
    do_import(admin, game, BASE)
    victim = points_of(game.id)[4]
    victim.timestamp_start, victim.not_filmed, victim.pull_play = 400, True, 'Flick'
    victim.injury_subs = {'off': ['Alice'], 'on': ['Cara']}
    db.session.add(Comment(game_id=game.id, point_id=victim.id, author_name='admin', content='keep me',
                           comment_type='Comment'))
    db.session.commit()
    victim_id = victim.id

    shorter = (',O,X,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\n\nCara,,2,2\n')
    html, token, text = preview(admin, game, shorter)
    # Consequences are explicit in the preview.
    assert '<b>1</b> hidden by reimport' in html and 'id="section-hidden"' in html
    assert 'hidden from everyone, not deleted' in html and 'restore them' in html
    assert '<td>400s</td>' not in html and 'no film' in html          # not-filmed shown instead of a time
    assert 'Comments kept' in html and '<td>1</td>' in html
    assert 'pull: Flick' in html and 'injury subs' in html
    assert 'name="confirm_hidden"' in html

    before = snapshot(db)
    refused = apply(admin, game, text, token, confirm=False)
    assert refused.status_code == 400 and b'Tick the confirmation box' in refused.data
    assert snapshot(db) == before

    assert apply(admin, game, text, token).status_code == 302
    pts = points_of(game.id)
    assert pts[4].id == victim_id and pts[4].hidden_by_import is True      # row survives
    assert (pts[4].timestamp_start, pts[4].not_filmed, pts[4].pull_play) == (400, True, 'Flick')
    assert pts[4].injury_subs == {'off': ['Alice'], 'on': ['Cara']} and names(pts[4]) == ['Alice', 'Cara']
    assert Comment.query.filter_by(point_id=victim_id).one().content == 'keep me'
    assert all(not pts[i].hidden_by_import for i in (1, 2, 3))


SHORTER = ',O,X,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\n\nCara,,2,2\n'


def render_context(app, client, path, template):
    from flask import template_rendered
    seen = []
    handler = lambda sender, template, context, **extra: seen.append((template.name, dict(context)))
    template_rendered.connect(handler, app)
    try:
        assert client.get(path).status_code == 200
    finally:
        template_rendered.disconnect(handler, app)
    return next(ctx for name, ctx in seen if name == template)


def test_hidden_points_disappear_from_every_read_and_write_path(admin, db, game, app):
    do_import(admin, game, BASE)
    victim_id = points_of(game.id)[4].id
    assert f'data-point-id="{victim_id}"' in admin.get(f'/film/games/{game.id}').get_data(as_text=True)
    do_import(admin, game, SHORTER)
    page = admin.get(f'/film/games/{game.id}').get_data(as_text=True)
    assert f'data-point-id="{victim_id}"' not in page
    api = f'/film/api/games/{game.id}'
    assert admin.patch(f'{api}/points/{victim_id}', json={'pull_play': 'x'}).status_code == 404
    assert admin.post(f'{api}/comments', json={'content': 'x', 'point_id': victim_id}).status_code == 404
    assert admin.post(f'{api}/update_player_sheet', json={'changes': [
        {'point_id': victim_id, 'player_name': 'Alice', 'in_point': False}]}).status_code == 404
    assert sorted(p.point_index for p in game.visible_points) == [1, 2, 3]
    assert game.points.count() == 4


def test_hidden_points_are_not_counted_in_team_and_player_statistics(admin, db, game, app):
    do_import(admin, game, BASE)
    ctx = render_context(app, admin, '/film/data', 'film_room/pages/tron_data.html')
    counts = lambda ctx: [(g['o_count'], g['d_count']) for g in ctx['games_with_stats'] if g['game'].id == game.id]
    assert counts(ctx) == [(2, 2)]
    assert {s['player'].name: s['total_pts'] for s in ctx['player_stats']} == {'Alice': 3, 'Bob': 2, 'Cara': 3}
    do_import(admin, game, SHORTER)
    ctx = render_context(app, admin, '/film/data', 'film_room/pages/tron_data.html')
    assert counts(ctx) == [(2, 1)]
    assert {s['player'].name: s['total_pts'] for s in ctx['player_stats']} == {'Alice': 2, 'Bob': 2, 'Cara': 2}


def test_restore_button_shows_a_hidden_point_again(admin, db, game, client_for):
    from flask_app.models import Comment
    do_import(admin, game, BASE)
    victim = points_of(game.id)[4]
    victim_id = victim.id
    db.session.add(Comment(game_id=game.id, point_id=victim_id, author_name='admin', content='kept',
                           comment_type='Comment'))
    db.session.commit()
    do_import(admin, game, ',O,X,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\n\nCara,,2,2\n')
    page = admin.get(url(game)).get_data(as_text=True)
    assert 'Points hidden by an earlier import' in page and 'Point 4' in page
    response = admin.post(url(game, f'points/{victim_id}/restore_hidden'))
    assert response.status_code == 302
    pts = points_of(game.id)
    assert pts[4].hidden_by_import is False and names(pts[4]) == ['Alice', 'Cara']
    assert Comment.query.filter_by(point_id=victim_id).one().content == 'kept'
    assert 'Points hidden by an earlier import' not in admin.get(url(game)).get_data(as_text=True)
    # A visible point cannot be "restored", and ids from other games are refused.
    assert admin.post(url(game, f'points/{victim_id}/restore_hidden')).status_code == 404


def test_a_hidden_point_that_reappears_in_the_csv_is_restored_and_listed(admin, db, game):
    do_import(admin, game, BASE)
    victim_id = points_of(game.id)[4].id
    do_import(admin, game, ',O,X,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\n\nCara,,2,2\n')
    html, token, text = preview(admin, game, BASE)
    assert 'id="section-restored"' in html and 'were hidden by an earlier import' in html
    assert apply(admin, game, text, token).status_code == 302
    p4 = points_of(game.id)[4]
    assert p4.id == victim_id and p4.hidden_by_import is False
    assert points_of(game.id)[4].point_index == 4 and len(points_of(game.id)) == 4


# ---------------------------------------------------------------------------
# stale previews
# ---------------------------------------------------------------------------

def edit_timestamp(client, game, point, value):
    return client.patch(f'/film/api/games/{game.id}/points/{point.id}', json={'timestamp_start': value})


def test_a_preview_goes_stale_after_a_point_edit(admin, db, game):
    do_import(admin, game, BASE)
    _, token, text = preview(admin, game, BASE)
    assert edit_timestamp(admin, game, points_of(game.id)[1], 55).status_code == 200
    before = snapshot(db)
    response = apply(admin, game, text, token)
    assert response.status_code == 409 and b'changed after the preview' in response.data
    assert snapshot(db) == before and points_of(game.id)[1].timestamp_start == 55


@pytest.mark.parametrize('edit', ['not_filmed', 'label', 'player_sheet', 'clear_sheet', 'other_import'])
def test_stale_preview_is_refused_for_every_kind_of_intervening_edit(admin, db, game, edit):
    do_import(admin, game, BASE)
    changing = BASE.replace('Alice,1,,1,2', 'Alice,1,,1,')   # a real change, so applying would write
    _, token, text = preview(admin, game, changing)
    p1 = points_of(game.id)[1]
    api = f'/film/api/games/{game.id}'
    if edit == 'not_filmed':
        assert admin.patch(f'{api}/points/{p1.id}', json={'not_filmed': True}).status_code == 200
    elif edit == 'label':
        assert admin.patch(f'{api}/points/{p1.id}', json={'defense_type': 'Zone'}).status_code == 200
    elif edit == 'player_sheet':
        assert admin.post(f'{api}/update_player_sheet', json={'changes': [
            {'point_id': p1.id, 'player_name': 'Cara', 'in_point': True}]}).status_code == 200
    elif edit == 'clear_sheet':
        assert admin.post(url(game, 'delete_player_sheet')).status_code == 302
    else:
        do_import(admin, game, BASE.replace('Bob,2,1,', 'Bob,2,,'))
    before = snapshot(db)
    response = apply(admin, game, text, token)
    assert response.status_code == 409
    assert snapshot(db) == before


def test_a_token_cannot_be_replayed_after_it_was_used(admin, db, game):
    do_import(admin, game, BASE)
    changing = BASE.replace('Alice,1,,1,2', 'Alice,1,,1,')
    _, token, text = preview(admin, game, changing)
    assert apply(admin, game, text, token).status_code == 302
    before = snapshot(db)
    assert apply(admin, game, text, token).status_code == 409
    assert snapshot(db) == before


def test_a_token_from_another_game_or_a_forged_token_is_refused(admin, db, game):
    from flask_app.models import Game
    other = Game(title='Other', opponent='Other')
    db.session.add(other)
    db.session.commit()
    do_import(admin, other, BASE)
    do_import(admin, game, BASE)
    _, other_token, text = preview(admin, other, BASE.replace('Alice,1,,1,2', 'Alice,1,,1,'))
    before = snapshot(db)
    assert apply(admin, game, text, other_token).status_code == 409
    assert apply(admin, game, text, '0' * 64).status_code == 409
    assert apply(admin, game, text, '').status_code == 409
    assert snapshot(db) == before


def test_the_token_does_not_depend_on_comments(admin, db, game):
    from flask_app.models import Comment
    do_import(admin, game, BASE)
    _, token, text = preview(admin, game, BASE)
    db.session.add(Comment(game_id=game.id, point_id=points_of(game.id)[1].id, author_name='admin',
                           content='later', comment_type='Comment'))
    db.session.commit()
    assert apply(admin, game, text, token).status_code == 302   # comments are never overwritten


# ---------------------------------------------------------------------------
# atomic apply
# ---------------------------------------------------------------------------

def test_a_failure_mid_apply_rolls_everything_back(admin, db, game, monkeypatch):
    from flask_app import film_routes
    do_import(admin, game, ',O\n,1\n,\n\nAlice,1\n')
    before = snapshot(db)
    calls = []

    def boom(player):
        calls.append(player.name)
        if len(calls) == 2:
            raise RuntimeError('synthetic failure')

    monkeypatch.setattr(film_routes, 'link_or_create_user_for_player', boom)
    _, token, text = preview(admin, game, ',O,X\n,1,\n,,2\n\nAlice,1,\nBob,,1\nCara,,2\n')
    response = apply(admin, game, text, token)
    assert response.status_code == 500 and b'nothing was changed' in response.data
    assert len(calls) == 2
    assert snapshot(db) == before  # no new points, players, roster rows, or order data


# ---------------------------------------------------------------------------
# access
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('role', ['anonymous', 'ordinary', 'leadership'])
def test_only_admins_can_preview_apply_or_restore(client_for, anonymous, db, game, role):
    do_import(client_for('admin'), game, BASE)
    victim = points_of(game.id)[4]
    victim.hidden_by_import = True
    db.session.commit()
    client = anonymous if role == 'anonymous' else client_for(role)
    before = snapshot(db)
    from io import BytesIO
    responses = [
        client.get(url(game)),
        client.post(url(game), data={'csv_file': (BytesIO(BASE.encode()), 'a.csv')},
                    content_type='multipart/form-data'),
        client.post(url(game, 'upload_csv/apply'), data={'csv_text': BASE, 'state_token': 'x', 'confirm_hidden': '1'}),
        client.post(url(game, f'points/{victim.id}/restore_hidden')),
    ]
    for response in responses:
        assert response.status_code in (302, 403), response.status_code  # redirected away, never served
    assert snapshot(db) == before


def test_restore_adds_the_points_players_to_the_sheet_order(admin, db, game):
    do_import(admin, game, BASE)
    victim_id = points_of(game.id)[4].id            # Alice and Cara played point 4
    # The reimport drops point 4 and Cara entirely, so she leaves the roster and the sheet order.
    do_import(admin, game, ',O,X,O\n,1,,3\n,,2,\n\nAlice,1,,1\nBob,2,1,\n')
    assert game.player_order_data == {'players': ['Alice', 'Bob'], 'separator_index': None}
    assert sorted(p.name for p in game.roster) == ['Alice', 'Bob']
    assert admin.post(url(game, f'points/{victim_id}/restore_hidden')).status_code == 302
    db.session.refresh(game)
    assert game.player_order_data == {'players': ['Alice', 'Bob', 'Cara'], 'separator_index': None}
    assert sorted(p.name for p in game.roster) == ['Alice', 'Bob', 'Cara']
    page = admin.get(f'/film/games/{game.id}').get_data(as_text=True)
    assert 'data-player="Cara"' in page and f'data-point-id="{victim_id}"' in page
