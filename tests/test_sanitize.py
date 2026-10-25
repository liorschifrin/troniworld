"""T05 slice 2: article HTML is reduced to an allowlist on save and on render.

All markup below is synthetic. Rejection cases assert that the dangerous part is
gone; allowed-formatting cases assert that the editor's output survives.
CKEDITOR40 transcribes the data shapes that CKEditor 5 classic 40.2.0 (the CDN
build in articles/editor.html) returns from getData(); they were written by hand
from that build's converters, not captured from a browser.
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
    'img-percent-traversal': ('<img src="/static/uploads/%2e%2e/%2e%2e/logout">', ['logout', '%2e']),
    'img-entity-traversal': ('<img src="/static/uploads/&#46;&#46;">', ['/static/uploads']),
    'img-subdirectory': ('<img src="/static/uploads/sub/a.png">', ['sub/a.png']),
    'img-query': ('<img src="/static/uploads/a.png?logout=1">', ['logout']),
    'img-percent-name': ('<img src="/static/uploads/a%20b.png">', ['a%20b']),
    'media-embed': ('<figure class="media"><oembed url="https://www.youtube.com/watch?v=x"></oembed></figure>',
                    ['oembed', 'youtube', 'figure']),
}

ALLOWED = {
    'p': ('<p>text</p>', '<p>text</p>'),
    'h1': ('<h1>t</h1>', '<h1>t</h1>'),
    'h2': ('<h2>t</h2>', '<h2>t</h2>'),
    'h3': ('<h3>t</h3>', '<h3>t</h3>'),
    'h4': ('<h4>t</h4>', '<h4>t</h4>'),
    'strong': ('<p><strong>b</strong></p>', '<p><strong>b</strong></p>'),
    'em': ('<p><em>i</em></p>', '<p><em>i</em></p>'),
    'i': ('<p><i>i</i></p>', '<p><i>i</i></p>'),
    'u': ('<p><u>u</u></p>', '<p><u>u</u></p>'),
    's': ('<p><s>s</s></p>', '<p><s>s</s></p>'),
    'ul-li': ('<ul><li>a</li><li>b</li></ul>', '<ul><li>a</li><li>b</li></ul>'),
    'ol-li': ('<ol><li>a</li></ol>', '<ol><li>a</li></ol>'),
    'blockquote': ('<blockquote><p>q</p></blockquote>', '<blockquote><p>q</p></blockquote>'),
    'br': ('<p>a<br>b</p>', '<p>a<br>b</p>'),
    'img': ('<img src="/static/uploads/a1b2.png" alt="A chart">',
            '<img src="/static/uploads/a1b2.png" alt="A chart">'),
}

LINKS = ['https://example.test/a?b=1&amp;c=2', 'http://example.test/', 'mailto:someone@example.test',
         '/post/3', 'post/3', '#section']

REL = ' rel="noopener noreferrer"'
UPLOAD = '/static/uploads/0f1e2d3c4b5a69788796a5b4c3d2e1f0_chart-2.png'

# name -> (CKEditor 40.2.0 getData() output, expected sanitized output, content removed?)
CKEDITOR40 = {
    'paragraph': ('<p>Plain text,&nbsp;spaced &amp; quoted "here".</p>',
                  '<p>Plain text,&nbsp;spaced &amp; quoted "here".</p>', False),
    'bold': ('<p>a <strong>bold</strong> word</p>', '<p>a <strong>bold</strong> word</p>', False),
    'italic': ('<p>an <i>italic</i> word</p>', '<p>an <i>italic</i> word</p>', False),
    'bold-italic': ('<p><strong><i>both</i></strong></p>', '<p><strong><i>both</i></strong></p>', False),
    'heading-1': ('<h2>Heading 1</h2>', '<h2>Heading 1</h2>', False),
    'heading-2': ('<h3>Heading 2</h3>', '<h3>Heading 2</h3>', False),
    'heading-3': ('<h4>Heading 3</h4>', '<h4>Heading 3</h4>', False),
    'link': ('<p><a href="https://example.test/page?a=1&amp;b=2">a link</a></p>',
             f'<p><a href="https://example.test/page?a=1&amp;b=2"{REL}>a link</a></p>', False),
    'bulleted-list': ('<ul><li>one</li><li>two<ul><li>nested</li></ul></li></ul>',
                      '<ul><li>one</li><li>two<ul><li>nested</li></ul></li></ul>', False),
    'numbered-list': ('<ol><li>first</li><li>second</li></ol>', '<ol><li>first</li><li>second</li></ol>', False),
    'block-quote': ('<blockquote><p>quoted</p></blockquote>', '<blockquote><p>quoted</p></blockquote>', False),
    'soft-break': ('<p>line<br>break</p>', '<p>line<br>break</p>', False),
    'empty-paragraph': ('<p>before</p><p>&nbsp;</p><p>after</p>', '<p>before</p><p>&nbsp;</p><p>after</p>', False),
    'block-image': (f'<figure class="image"><img style="aspect-ratio:640/480;" src="{UPLOAD}" width="640" height="480"></figure>',
                    f'<img src="{UPLOAD}">', False),
    'block-image-alt': (f'<figure class="image"><img src="{UPLOAD}" alt="A chart"></figure>',
                        f'<img src="{UPLOAD}" alt="A chart">', False),
    'inline-image': (f'<p>see <img style="aspect-ratio:32/32;" src="{UPLOAD}" alt="icon" width="32" height="32"> here</p>',
                     f'<p>see <img src="{UPLOAD}" alt="icon"> here</p>', False),
    'image-caption': (f'<figure class="image"><img src="{UPLOAD}"><figcaption>Caption</figcaption></figure>',
                      f'<img src="{UPLOAD}">Caption', True),
    'table': ('<figure class="table"><table><tbody><tr><td>a</td><td>b</td></tr></tbody></table></figure>',
              'ab', True),
    'media-embed': ('<figure class="media"><oembed url="https://www.youtube.com/watch?v=x"></oembed></figure>',
                    '', True),
}
CKEDITOR40_KEPT = [name for name in CKEDITOR40 if not CKEDITOR40[name][2]]
CKEDITOR40_DOCUMENT = ''.join(CKEDITOR40[name][0] for name in CKEDITOR40_KEPT)
CKEDITOR40_EXPECTED = ''.join(CKEDITOR40[name][1] for name in CKEDITOR40_KEPT)
ALTERED_MESSAGE = 'Some markup in the content is not allowed and was removed. Check the post.'
DISALLOWED_MESSAGE = 'Content contained only disallowed markup.'


def flashes(client):
    """Return and clear the messages flashed to `client`."""
    with client.session_transaction() as session:
        return [message for _, message in session.pop('_flashes', [])]


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


@pytest.mark.parametrize('name', CKEDITOR40)
def test_sanitizer_handles_ckeditor40_output(name):
    from flask_app.sanitize import removed_content, sanitize_html
    source, expected, removed = CKEDITOR40[name]
    assert sanitize_html(source) == expected
    assert removed_content(source, sanitize_html(source)) is removed


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


def test_ckeditor40_document_renders_formatted(anonymous, saved_posts):
    post_id = saved_posts(CKEDITOR40_DOCUMENT)
    html = anonymous.get(f'/post/{post_id}').get_data(as_text=True)
    assert f'<div>{CKEDITOR40_EXPECTED}</div>' in html


def test_ckeditor40_document_is_created_formatted_without_warning(admin, db):
    response = admin.post('/new_post', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'content': CKEDITOR40_DOCUMENT})
    assert response.status_code == 302
    assert Post.query.one().content == CKEDITOR40_EXPECTED
    assert flashes(admin) == ['Post created.']


def test_ckeditor40_document_is_edited_formatted_without_warning(admin, db, saved_posts):
    post_id = saved_posts('<p>old</p>')
    response = admin.post(f'/post/{post_id}/edit', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'created_at': '2026-01-02',
        'content': CKEDITOR40_DOCUMENT})
    assert response.status_code == 302
    assert db.session.get(Post, post_id).content == CKEDITOR40_EXPECTED
    assert flashes(admin) == ['Post updated.']


@pytest.mark.parametrize('name', ['image-caption', 'table'])
def test_save_warns_when_content_is_removed(admin, db, saved_posts, name):
    source, expected, _ = CKEDITOR40[name]
    content = '<p>kept</p>' + source
    admin.post('/new_post', data={'title': 'Synthetic title', 'author': 'Synthetic author', 'content': content})
    assert Post.query.one().content == '<p>kept</p>' + expected
    assert flashes(admin) == ['Post created.', ALTERED_MESSAGE]
    post_id = saved_posts('<p>old</p>')
    admin.post(f'/post/{post_id}/edit', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'created_at': '2026-01-02', 'content': content})
    assert db.session.get(Post, post_id).content == '<p>kept</p>' + expected
    assert flashes(admin) == ['Post updated.', ALTERED_MESSAGE]


@pytest.mark.parametrize('content', [
    '<script>alert(1)</script>',
    '<iframe src="https://evil.test"></iframe>',
    '<img src="https://evil.test/track.png">',
    '<p><img src="/static/uploads/%2e%2e/logout"></p>',
    CKEDITOR40['media-embed'][0],
])
def test_content_that_sanitizes_to_nothing_is_rejected(admin, db, saved_posts, content):
    response = admin.post('/new_post', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'content': content})
    assert response.status_code == 302 and response.location.endswith('/new_post')
    assert Post.query.count() == 0
    assert flashes(admin) == [DISALLOWED_MESSAGE]
    post_id = saved_posts('<p>old</p>')
    response = admin.post(f'/post/{post_id}/edit', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'created_at': '2026-01-02', 'content': content})
    assert response.location.endswith(f'/post/{post_id}/edit')
    assert db.session.get(Post, post_id).content == '<p>old</p>'
    assert flashes(admin) == [DISALLOWED_MESSAGE]


@pytest.mark.parametrize('content', ['', '   ', '<p></p>', '<p>&nbsp;</p>', '<p> </p><p><br></p>'])
def test_content_without_text_or_image_is_empty(admin, db, saved_posts, content):
    admin.post('/new_post', data={'title': 'Synthetic title', 'author': 'Synthetic author', 'content': content})
    assert Post.query.count() == 0
    assert flashes(admin) == ['Title, author, and content are required.']
    post_id = saved_posts('<p>old</p>')
    admin.post(f'/post/{post_id}/edit', data={
        'title': 'Synthetic title', 'author': 'Synthetic author', 'created_at': '2026-01-02', 'content': content})
    assert db.session.get(Post, post_id).content == '<p>old</p>'
    assert flashes(admin) == ['Title, author, content, and date are required.']


def test_image_only_content_is_accepted(admin, db):
    source, expected, _ = CKEDITOR40['block-image']
    admin.post('/new_post', data={'title': 'Synthetic title', 'author': 'Synthetic author', 'content': source})
    assert Post.query.one().content == expected


def test_edit_form_loads_sanitized_markup_escaped(admin, saved_posts):
    post_id = saved_posts('<p>a</p><script>alert(1)</script><p onclick="x()">b &lt;i&gt;</p>'
                          + CKEDITOR40['italic'][0])
    html = admin.get(f'/post/{post_id}/edit').get_data(as_text=True)
    textarea = html[html.index('<textarea id="content-editor"'):html.index('</textarea>')]
    assert 'alert' not in textarea and 'onclick' not in textarea and 'script' not in textarea
    assert textarea.endswith('>&lt;p&gt;a&lt;/p&gt;&lt;p&gt;b &amp;lt;i&amp;gt;&lt;/p&gt;'
                             '&lt;p&gt;an &lt;i&gt;italic&lt;/i&gt; word&lt;/p&gt;')


@pytest.mark.parametrize('path', ['/new_post', 'edit'])
def test_editor_offers_no_tables_or_media_embeds(admin, saved_posts, path):
    if path == 'edit':
        path = f'/post/{saved_posts("<p>x</p>")}/edit'
    html = admin.get(path).get_data(as_text=True)
    assert "var ARTICLE_EDITOR_REMOVED_PLUGINS = ['Table', 'TableToolbar', 'MediaEmbed'];" in html
    assert "var ARTICLE_EDITOR_REMOVED_TOOLBAR_ITEMS = ['insertTable', 'mediaEmbed'];" in html
    config = html[html.index('ClassicEditor.create('):]
    config = config[:config.index('})')]
    assert 'removePlugins: ARTICLE_EDITOR_REMOVED_PLUGINS' in config
    assert 'toolbar: { removeItems: ARTICLE_EDITOR_REMOVED_TOOLBAR_ITEMS }' in config
    assert html.count('ClassicEditor.create(') == 1


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
