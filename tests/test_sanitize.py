"""T05 slice 2: article HTML is reduced to an allowlist on save and on render.

All markup below is synthetic. Rejection cases assert that the dangerous part is
gone; allowed-formatting cases assert that the editor's output survives.
"""
from pathlib import Path
import re

import pytest

from flask_app.models import ArticleComment, Post

TEMPLATES = Path(__file__).resolve().parents[1] / 'flask_app/templates'

HOSTILE = {
    'script-tag': ('<p>ok</p><script>alert(1)</script>', ['<script', 'alert(1)']),
    'script-uppercase': ('<SCRIPT SRC=//evil.test/x.js></SCRIPT><p>ok</p>', ['script', 'evil.test']),
    'img-onerror': ('<img src="/static/uploads/a.png" onerror="alert(1)">', ['onerror', 'alert']),
    'p-onclick': ('<p onclick="alert(1)">ok</p>', ['onclick', 'alert']),
    'body-onload': ('<svg onload=alert(1)><p>ok</p>', ['svg', 'onload', 'alert']),
    'javascript-href': ('<a href="javascript:alert(1)">x</a>', ['javascript']),
    'javascript-mixed-case': ('<a href="JaVa\tScRiPt:alert(1)">x</a>', ['script:', 'alert']),
    'javascript-entity': ('<a href="&#106;avascript:alert(1)">x</a>', ['avascript', 'alert']),
    'data-href': ('<a href="data:text/html,<script>alert(1)</script>">x</a>', ['data:', 'alert']),
    'data-img': ('<img src="data:image/svg+xml;base64,PHN2Zz4=">', ['data:']),
    'vbscript': ('<a href="vbscript:x">x</a>', ['vbscript']),
    'style-attr': ('<p style="background:url(javascript:alert(1))">x</p>', ['style', 'javascript']),
    'class-id-attrs': ('<p class="a" id="b" data-x="c">x</p>', ['class', 'id=', 'data-x']),
    'style-tag': ('<style>p{color:red}</style><p>x</p>', ['<style', 'color:red']),
    'iframe': ('<iframe src="https://evil.test"></iframe><p>x</p>', ['iframe', 'evil.test']),
    'object-embed': ('<object data="x"></object><embed src="x">', ['object', 'embed']),
    'form': ('<form action="https://evil.test"><input name="a"></form>', ['form', 'input', 'evil.test']),
    'table': ('<table><tr><td>cell</td></tr></table>', ['<table', '<tr', '<td']),
    'comment': ('<!-- hidden --><p>x</p>', ['<!--', 'hidden']),
    'nested-broken': ('<p><b><i>a</p></scr<script>ipt><script>alert(1)</script>', ['<script', 'alert(1)']),
    'unclosed-attr': ('<img src="/static/uploads/a.png" alt="x onerror=alert(1)>', ['onerror=alert', '<script']),
    'img-external': ('<img src="https://evil.test/track.png">', ['evil.test']),
    'img-protocol-relative': ('<img src="//evil.test/a.png">', ['evil.test']),
    'img-other-path': ('<img src="/static/images/logo.png">', ['/static/images']),
    'img-prefix-lookalike': ('<img src="/static/uploadsX/a.png">', ['uploadsX']),
    'img-traversal': ('<img src="/static/uploads/../../etc/passwd">', ['passwd']),
    'img-relative': ('<img src="static/uploads/a.png">', ['static/uploads']),
}

ALLOWED = {
    'p': ('<p>text</p>', '<p>text</p>'),
    'h1': ('<h1>t</h1>', '<h1>t</h1>'),
    'h2': ('<h2>t</h2>', '<h2>t</h2>'),
    'h3': ('<h3>t</h3>', '<h3>t</h3>'),
    'strong': ('<p><strong>b</strong></p>', '<p><strong>b</strong></p>'),
    'em': ('<p><em>i</em></p>', '<p><em>i</em></p>'),
    'u': ('<p><u>u</u></p>', '<p><u>u</u></p>'),
    's': ('<p><s>s</s></p>', '<p><s>s</s></p>'),
    'ul-li': ('<ul><li>a</li><li>b</li></ul>', '<ul><li>a</li><li>b</li></ul>'),
    'ol-li': ('<ol><li>a</li></ol>', '<ol><li>a</li></ol>'),
    'blockquote': ('<blockquote><p>q</p></blockquote>', '<blockquote><p>q</p></blockquote>'),
    'br': ('<p>a<br>b</p>', '<p>a<br>b</p>'),
    'img': ('<img src="/static/uploads/a1b2.png" alt="A chart">',
            '<img src="/static/uploads/a1b2.png" alt="A chart">'),
}

LINKS = ['https://example.test/a?b=1&amp;c=2', 'http://example.test/', 'mailto:someone@example.test']


@pytest.fixture
def saved_posts(db):
    def add(content):
        post = Post(title='Synthetic title', author='Synthetic author', content=content)
        db.session.add(post)
        db.session.commit()
        return post.id
    return add


@pytest.mark.parametrize('name', HOSTILE)
def test_sanitizer_removes_hostile_markup(name):
    from flask_app.sanitize import sanitize_html
    markup, forbidden = HOSTILE[name]
    result = sanitize_html(markup).lower()
    for fragment in forbidden:
        assert fragment.lower() not in result


@pytest.mark.parametrize('name', ALLOWED)
def test_sanitizer_keeps_editor_formatting(name):
    from flask_app.sanitize import sanitize_html
    source, expected = ALLOWED[name]
    assert sanitize_html(source) == expected


@pytest.mark.parametrize('href', LINKS)
def test_sanitizer_keeps_safe_links(href):
    from flask_app.sanitize import sanitize_html
    result = sanitize_html(f'<p><a href="{href}">go</a></p>')
    assert f'href="{href}"' in result and '>go</a>' in result


def test_sanitizer_handles_empty_and_plain_text():
    from flask_app.sanitize import sanitize_html
    assert sanitize_html(None) == '' and sanitize_html('') == ''
    assert sanitize_html('a &lt;script&gt; b') == 'a &lt;script&gt; b'


@pytest.mark.parametrize('name', HOSTILE)
def test_stored_markup_is_sanitized_when_rendered(admin, anonymous, db, saved_posts, name):
    markup, forbidden = HOSTILE[name]
    post_id = saved_posts('<p>marker-text</p>' + markup)
    html = anonymous.get(f'/post/{post_id}').get_data(as_text=True)
    start = html.index('marker-text')
    body = html[start:html.index('</div>', start)].lower()
    for fragment in forbidden:
        assert fragment.lower() not in body
    # Stored value is not rewritten by rendering.
    assert db.session.get(Post, post_id).content == '<p>marker-text</p>' + markup


def test_stored_allowed_markup_renders_unchanged(anonymous, saved_posts):
    source = ''.join(ALLOWED[name][0] for name in ALLOWED)
    post_id = saved_posts(source)
    html = anonymous.get(f'/post/{post_id}').get_data(as_text=True)
    for name, (_, expected) in ALLOWED.items():
        assert expected in html, name


@pytest.mark.parametrize('name', HOSTILE)
def test_create_sanitizes_content_before_saving(admin, db, name):
    markup, forbidden = HOSTILE[name]
    response = admin.post('/new_post', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'content': '<p>marker-text</p>' + markup})
    assert response.status_code == 302
    stored = Post.query.one().content.lower()
    assert 'marker-text' in stored
    for fragment in forbidden:
        assert fragment.lower() not in stored


@pytest.mark.parametrize('name', HOSTILE)
def test_edit_sanitizes_content_before_saving(admin, db, saved_posts, name):
    markup, forbidden = HOSTILE[name]
    post_id = saved_posts('<p>old</p>')
    response = admin.post(f'/post/{post_id}/edit', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'created_at': '2026-01-02',
        'content': '<p>marker-text</p>' + markup})
    assert response.status_code == 302
    stored = db.session.get(Post, post_id).content.lower()
    assert 'marker-text' in stored
    for fragment in forbidden:
        assert fragment.lower() not in stored


def test_save_keeps_allowed_formatting(admin, db):
    source = ''.join(ALLOWED[name][0] for name in ALLOWED)
    admin.post('/new_post', data={'title': 'Synthetic title', 'author': 'Synthetic author', 'content': source})
    assert Post.query.one().content == ''.join(ALLOWED[name][1] for name in ALLOWED)


def test_content_that_sanitizes_to_nothing_is_rejected(admin, db):
    response = admin.post('/new_post', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'content': '<script>alert(1)</script>'})
    assert response.status_code == 302
    assert Post.query.count() == 0


def test_edit_form_shows_stored_markup_escaped(admin, saved_posts):
    post_id = saved_posts('<p>a</p><script>alert(1)</script>')
    html = admin.get(f'/post/{post_id}/edit').get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html


def test_post_template_has_no_unfiltered_safe_output():
    for path in TEMPLATES.rglob('*.html'):
        source = path.read_text()
        for match in re.finditer(r'\{\{[^}]*\|\s*safe\b[^}]*\}\}', source):
            assert 'post.content' not in match.group(0), path


def test_comment_text_stays_escaped(anonymous, admin, saved_posts, db):
    post_id = saved_posts('<p>body</p>')
    db.session.add(ArticleComment(post_id=post_id, author_name='ordinary', content='<script>alert(1)</script><b>x</b>'))
    db.session.commit()
    page = anonymous.get(f'/post/{post_id}').get_data(as_text=True)
    assert 'alert(1)' not in page
    api = anonymous.get(f'/post/{post_id}/comments')
    assert api.status_code == 200
    assert api.mimetype == 'application/json'
    assert '<script>alert(1)</script><b>x</b>' in api.get_data(as_text=True).replace('\\u003c', '<')
    source = (TEMPLATES / 'articles/post.html').read_text()
    assert 'esc(c.content)' in source and 'esc(r.content)' in source
    assert 'sanitize_html' not in source.split('async function loadComments')[1]
