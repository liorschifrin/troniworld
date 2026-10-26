"""Render actual template/JS functions with synthetic stored injection strings.

Node executes pure rendering functions with minimal DOM stubs, not a browser or server.
HTMLParser decodes attribute entities as a browser does before checking handler text.
"""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess

import pytest

from template_source import expanded_source, player_script_source

ROOT = Path(__file__).resolve().parents[1]
GAME = 'film_room/pages/game_player.html'
ATTACK = '\'");T04_PAYLOAD();//<img src=x onerror="T04_PAYLOAD()">'


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    @property
    def handlers(self):
        return [value for _, attrs in self.elements for key, value in attrs.items() if key.startswith('on')]


def source(template):
    return player_script_source() if template == GAME else expanded_source(template)


def functions(template, *names):
    text = source(template)
    return '\n'.join(re.search(r'^( {0,2})function ' + name + r'\([^\n]*\) \{.*?^\1\}', text, re.M | re.S)[0]
                     for name in names)


def node_html(code):
    result = subprocess.run(['node', '-'], input=code, text=True, capture_output=True, check=True)
    return result.stdout


def safe_handlers(html):
    parsed = Elements(html)
    assert parsed.handlers  # Prevent a vacuous check.
    assert all('T04_PAYLOAD' not in handler for handler in parsed.handlers)
    assert not any(tag == 'img' for tag, _ in parsed.elements)
    return parsed


@pytest.mark.parametrize('path', ['/film/analytics', '/admin/users'])
def test_stored_username_is_data_not_handler(admin, records, db, path):
    records['users']['ordinary'].username = ATTACK
    db.session.commit()
    response = admin.get(path)
    assert response.status_code == 200
    parsed = safe_handlers(response.text)
    assert any(attrs.get('data-username') == ATTACK for _, attrs in parsed.elements)
    assert records['users']['ordinary'].username == ATTACK  # No stored-data cleanup.


@pytest.mark.parametrize('stored', ['0);T04_PAYLOAD();//', -1, 86401, float('inf')])
def test_legacy_point_timestamp_never_becomes_code(admin, records, db, stored):
    from flask_app.models import Player
    player = Player(name='Synthetic roster')
    records['game'].roster.append(player)
    records['point'].timestamp_start = stored
    db.session.add(player)
    db.session.commit()
    response = admin.get(f'/film/games/{records["game"].id}')
    assert response.status_code == 200
    parsed = safe_handlers(response.text)
    assert not any('seekToPointTimestamp(' in h for h in parsed.handlers)
    assert 'timestamp_start: null' in response.text
    db.session.refresh(records['point'])
    assert records['point'].timestamp_start == stored


@pytest.mark.parametrize('timestamp', ['0);T04_PAYLOAD();//', ATTACK, '12', -1, 86401, None, 12.5])
def test_comment_html_does_not_execute_stored_text(timestamp):
    comment = dict(id=7, timestamp=timestamp, author_name=ATTACK, content=ATTACK,
                   created_at='2026-01-01', private_to=[ATTACK], replies=[])
    code = '''
const currentUserName = null, opponentName = '', isAdmin = true, isCurrentUserLeadership = false;
const expandedThreads = new Set(), activeReplyInputId = 7;
''' + functions(GAME, 'escHtml', 'parseMentions', 'formatTimestamp', 'relativeTime', 'renderCommentThread')
    html = node_html(code + '\nconsole.log(renderCommentThread(' + json.dumps(comment) + '));')
    parsed = safe_handlers(html)
    assert any(attrs.get('data-placeholder') == 'Reply to ' + ATTACK + '...' for _, attrs in parsed.elements)
    seek = [h for h in parsed.handlers if h.startswith('seekToTime(')]
    assert seek == (['seekToTime(12.5)'] if timestamp == 12.5 else [])


@pytest.mark.parametrize('renderer', ['renderMentionDropdown', 'renderPrivateUserDropdown'])
def test_autocomplete_username_is_data(renderer):
    setup = '''
const opponentName = '';
const inputEl = {getBoundingClientRect: () => ({}), closest: () => null, parentElement: null,
  setAttribute: () => {}, removeAttribute: () => {}};
const window = {getSelection: () => null};
const dropdown = {innerHTML: '', style: {}, querySelector: () => null};
const mentionDropdownEl = dropdown, privateUserDropdownEl = dropdown;
function _positionMentionDropdown() {}
'''
    setup += 'const mentionState = {filteredUsers: [' + json.dumps(ATTACK) + '], selectedIndex: 0};\n'
    setup += 'const privateUserDropState = {filtered: [' + json.dumps(ATTACK) + '], selectedIndex: 0};\n'
    html = node_html(setup + functions(GAME, 'escHtml', renderer) + '\n' + renderer + '(inputEl); console.log(dropdown.innerHTML);')
    parsed = safe_handlers(html)
    assert any(attrs.get('data-user') == ATTACK for _, attrs in parsed.elements)
    assert all('this.dataset.user' in handler for handler in parsed.handlers)


@pytest.mark.parametrize('template', ['film_room/pages/login.html', 'articles/login_articles.html'])
def test_login_autocomplete_username_is_data(template):
    setup = "const drop = {innerHTML: '', style: {}, querySelector: () => ({classList: {add() {}}})}; let activeIdx;\n"
    # Baseline lacks escapeUser: include it only when present so baseline exercises its unsafe renderer.
    names = ['escapeUser', 'showDrop'] if 'function escapeUser(' in source(template) else ['showDrop']
    html = node_html(setup + functions(template, *names) + '\nshowDrop([' + json.dumps(ATTACK) + ']); console.log(drop.innerHTML);')
    parsed = safe_handlers(html)
    assert any(attrs.get('data-user') == ATTACK for _, attrs in parsed.elements)


@pytest.mark.parametrize('editing', [False, True])
def test_article_comment_and_reply_content_is_text(editing):
    template = 'articles/post.html'
    comment = dict(id=7, author_name=ATTACK, content=ATTACK, created_at='2026-01-01', replies=[])
    setup = f'const CURRENT_USER = {json.dumps(ATTACK)}, IS_ADMIN = true, activeEditId = {7 if editing else "null"}, activeReplyId = 7;\n'
    code = setup + functions(template, 'esc', 'relTime', 'renderComment', 'renderReply')
    html = node_html(code + '\nconsole.log(renderComment(' + json.dumps(comment) + '));\nconsole.log(renderReply(' + json.dumps(comment) + '));')
    safe_handlers(html)
