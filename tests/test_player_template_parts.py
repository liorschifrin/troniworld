"""T11: the player page is assembled from partials; nothing was lost or duplicated.

No browser runs. These checks are source-level and Node-level: every partial is
included exactly once in a fixed order, top-level script names are declared once,
and the script the page serves still parses (``node --check``) and defines the
functions the page's inline handlers call.
"""
from collections import Counter
from pathlib import Path
import re
import subprocess

import pytest

from template_source import PLAYER_MODULES, TEMPLATES, expanded_source

PAGE = 'film_room/pages/game_player.html'
PARTIALS = TEMPLATES / 'film_room/partials/game_player'
JS_ORDER = ['state', 'mentions', 'player_sheet', 'watch_time', 'video', 'comments', 'points',
            'bootstrap', 'scoreboard']


def includes(template):
    return re.findall(r"\{% include '([^']+)' %\}", (TEMPLATES / template).read_text())


def test_page_includes_every_partial_once_in_order():
    found = includes(PAGE)
    expected = ['_styles', '_markup'] + [f'_js_{name}' for name in JS_ORDER]
    assert sorted(found) == sorted(f'film_room/partials/game_player/{n}.html' for n in expected)
    assert [Path(f).stem for f in found if Path(f).stem.startswith('_js_')] == [f'_js_{n}' for n in JS_ORDER]
    assert {p.stem for p in PARTIALS.glob('*.html')} == set(expected)  # no orphans


def test_page_file_is_a_thin_shell():
    shell = (TEMPLATES / PAGE).read_text()
    assert len(shell.splitlines()) < 60
    assert 'function ' not in shell and '{' not in shell.replace('{%', '').replace('{{', '').replace('%}', '')


def script_partials():
    return {n: (PARTIALS / f'_js_{n}.html').read_text() for n in JS_ORDER}


def test_top_level_script_names_are_declared_once():
    names = Counter()
    for text in script_partials().values():
        names.update(re.findall(r'^  (?:async )?function (\w+)\(', text, re.M))
        names.update(re.findall(r'^  (?:const|let) (\w+)\b', text, re.M))
    for module in PLAYER_MODULES.glob('*.js'):
        names.update(re.findall(r'^(?:async )?function (\w+)\(', module.read_text(), re.M))
    # pointPlayersData is declared in both branches of one {% if player_sheet_data %}.
    assert [n for n, count in names.items() if count > 1] == ['pointPlayersData']
    assert len(names) > 100  # guards a vacuous pass


def test_jinja_blocks_balance_inside_each_partial():
    for name, text in script_partials().items():
        opened = len(re.findall(r'\{%-?\s*(?:if|for)\b', text))
        closed = len(re.findall(r'\{%-?\s*end(?:if|for)\b', text))
        assert opened == closed, name


@pytest.fixture
def served_script(records, admin, db):
    from flask_app.models import Player, Point
    player = Player(name='Synthetic Player')
    db.session.add(player)
    db.session.flush()
    records['point'].players.append(player)
    records['game'].youtube_id = 'aaaaaaaaaaa'
    db.session.commit()
    response = admin.get(f"/film/games/{records['game'].id}")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    return max(scripts, key=len)


def test_served_script_parses_in_node(served_script, tmp_path):
    path = tmp_path / 'player.js'
    path.write_text(served_script)
    result = subprocess.run(['node', '--check', str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_served_scripts_define_what_the_markup_calls(served_script, records, admin):
    html = admin.get(f"/film/games/{records['game'].id}").get_data(as_text=True)
    # The page also loads the notification bell and menu scripts from the base template.
    served_script = '\n'.join(re.findall(r'<script>(.*?)</script>', html, re.S))
    called = set(re.findall(
        r'on(?:click|input|keydown|change|keyup|blur)="\s*(?:event\.\w+\(\);\s*)?(\w+)\(', html))
    defined = set(re.findall(r'function (\w+)\(', served_script))
    assert {'enterPlayerSheetEdit', 'toggleAddMenu'} <= called  # handlers behind an event.stopPropagation() prefix
    assert called and called <= defined, called - defined


def test_source_ordering_matches_the_template_the_browser_receives():
    text = expanded_source(PAGE)
    positions = [text.index(f'function {fn}(') for fn in
                 ('parseMentions', 'enterPlayerSheetEdit', 'sendWatchTimeTracking', 'loadVideo',
                  'renderComments', 'setPointTimestamp', 'scrollToCommentById', 'updateScoreboard')]
    assert positions == sorted(positions)
    assert text.rstrip().endswith('{% endblock %}')


def test_static_modules_load_before_the_inline_script_and_are_served(admin, records):
    html = admin.get(f"/film/games/{records['game'].id}").get_data(as_text=True)
    sources = re.findall(r'<script src="(/static/js/game_player/[^"]+)"', html)
    assert sources == ['/static/js/game_player/format.js', '/static/js/game_player/scoreboard.js']
    inline = html.index('let player = null;')
    assert all(html.index(src) < inline for src in sources)
    for src in sources:
        response = admin.get(src)
        assert response.status_code == 200 and b'function ' in response.data
        response.close()
