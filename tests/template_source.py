"""Template text with ``{% include %}`` lines expanded, for source-level checks.

The player page is assembled from partials (T11). Tests that scan or extract
its JavaScript read the assembled text, so they keep checking what the browser gets.
"""
import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / 'flask_app/templates'
PLAYER_MODULES = Path(__file__).resolve().parents[1] / 'flask_app/static/js/game_player'
INCLUDE = re.compile(r"^[ \t]*\{% include '([^']+)' %\}[ \t]*$", re.M)


def expanded_source(template):
    def inline(match):
        included = expanded_source(match.group(1))
        # Jinja drops one trailing newline from an included file; the include line keeps its own.
        return included[:-1] if included.endswith('\n') else included
    return INCLUDE.sub(inline, (TEMPLATES / template).read_text())


def player_script_source():
    """The assembled player template plus the static modules it loads before its inline script."""
    modules = '\n'.join(path.read_text() for path in sorted(PLAYER_MODULES.glob('*.js')))
    return modules + '\n' + expanded_source('film_room/pages/game_player.html')
