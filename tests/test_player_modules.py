"""T11: the pure player-page modules in flask_app/static/js/game_player run under Node.

The real files are loaded unchanged into a Node VM context; no browser, DOM or
YouTube player is involved, so these cover the arithmetic and formatting only.
"""
import json
import subprocess

import pytest

from template_source import PLAYER_MODULES


def run(module, expression):
    code = f"""
const vm = require('vm');
const fs = require('fs');
const context = vm.createContext({{ console, Date, Math, Number, JSON }});
vm.runInContext(fs.readFileSync({json.dumps(str(PLAYER_MODULES / module))}, 'utf8'), context);
console.log(JSON.stringify(vm.runInContext({json.dumps(expression)}, context)));
"""
    result = subprocess.run(['node', '-'], input=code, text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


POINTS = [{'tron_point': True, 'timestamp_start': 10}, {'tron_point': False, 'timestamp_start': 60},
          {'tron_point': True, 'timestamp_start': None}, {'tron_point': True, 'timestamp_start': 120}]


@pytest.mark.parametrize('now,duration,expected', [
    (5, 200, []),                  # before the first timestamped point
    (10, 200, []),                 # inside point 1: it is still in progress
    (60, 200, [0]),                # exactly at point 2's timestamp counts as reached
    (65, 200, [0]),                # inside point 2: point 1 is complete
    (130, 200, [0, 1, 2]),         # inside point 4, the untimed point 3 counts as complete
    (150, 150, [0, 1, 2, 3]),      # video ending: the true final score
])
def test_completed_points(now, duration, expected):
    got = run('scoreboard.js', f'getCompletedPoints({json.dumps(POINTS)}, {now}, {duration})')
    assert got == [POINTS[i] for i in expected]


def test_score_counts_scored_and_conceded_points():
    assert run('scoreboard.js', f'getCurrentScore({json.dumps(POINTS)})') == {'tron': 3, 'opp': 1}
    assert run('scoreboard.js', 'getCurrentScore([])') == {'tron': 0, 'opp': 0}


@pytest.mark.parametrize('point,expected', [
    ({'timestamp_start': 12}, 12), ({'timestamp_start': '12'}, 12), ({'timestamp_start': ''}, None),
    ({'timestamp_start': None}, None), ({'timestamp_start': 'abc'}, None), ({}, None), (None, None),
])
def test_timestamp_value(point, expected):
    assert run('scoreboard.js', f'getTimestampValue({json.dumps(point)})') == expected


@pytest.mark.parametrize('call,expected', [
    ('formatTime(0)', '0:00'), ('formatTime(-3)', '0:00'), ('formatTime(65.9)', '1:05'),
    ('formatTime(3600)', '60:00'),
    ('formatTimestamp(0)', '0:00'), ('formatTimestamp(null)', None), ('formatTimestamp(754)', '12:34'),
    ('escHtml(`<a href="x">&</a>`)', '&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;'),
    ('extractVideoId("dQw4w9WgXcQ")', 'dQw4w9WgXcQ'),
    ('extractVideoId(" https://youtu.be/dQw4w9WgXcQ?t=3 ")', 'dQw4w9WgXcQ'),
    ('extractVideoId("https://www.youtube.com/watch?v=dQw4w9WgXcQ&x=1")', 'dQw4w9WgXcQ'),
    ('extractVideoId("https://www.youtube.com/embed/dQw4w9WgXcQ")', 'dQw4w9WgXcQ'),
    ('extractVideoId("not a video")', None),
    ('relativeTime("")', ''), ('relativeTime("garbage")', 'garbage'),
])
def test_format_helpers(call, expected):
    assert run('format.js', call) == expected


def test_relative_time_buckets():
    for offset_seconds, expected in ((5, 'just now'), (5 * 60, '5m ago'), (3 * 3600, '3h ago'), (2 * 86400, '2d ago')):
        assert run('format.js', f'relativeTime(new Date(Date.now() - {offset_seconds * 1000}).toISOString())') == expected
    assert run('format.js', 'relativeTime("2020-03-04T12:00:00Z")') in ('Mar 4', 'Mar 3')
