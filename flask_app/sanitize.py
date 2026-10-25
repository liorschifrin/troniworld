"""Allowlist sanitizer for article HTML (T05 slice 2).

The allowed markup covers the CKEditor 5 classic 40.2.0 output the article
editor can produce once tables and media embeds are removed from its toolbar
(see tests/test_sanitize.py for the real output shapes), plus h1, u, and s.
Everything else (scripts, styles, tables, embeds, figure wrappers, event
handlers, class/style/id attributes, javascript:/data: URLs) is removed. Stored
content is never rewritten by a migration; existing rows are sanitized when
rendered.
"""
from collections import Counter
from html.parser import HTMLParser
import re

import nh3
from markupsafe import Markup

ALLOWED_TAGS = {
    'p', 'h1', 'h2', 'h3', 'h4', 'strong', 'em', 'i', 'u', 's',
    'ul', 'ol', 'li', 'a', 'blockquote', 'br', 'img',
}
ALLOWED_ATTRIBUTES = {'a': {'href'}, 'img': {'src', 'alt'}}
ALLOWED_URL_SCHEMES = {'http', 'https', 'mailto'}
UPLOAD_SRC = re.compile(r'/static/uploads/[A-Za-z0-9._-]+')

# CKEditor 40 wraps block images in <figure class="image"> and adds width,
# height, and an aspect-ratio style to uploaded images. Dropping these keeps the
# image itself, so it is not reported as lost content.
_BENIGN_TAGS = {'figure'}
_BENIGN_ATTRIBUTES = {('figure', 'class'), ('img', 'width'), ('img', 'height'), ('img', 'style')}


def _filter_attribute(tag, attribute, value):
    if tag == 'img' and attribute == 'src':
        if not UPLOAD_SRC.fullmatch(value) or '..' in value:
            return None
    return value


def sanitize_html(text):
    """Return the allowlisted subset of `text` as a plain string."""
    if not text:
        return ''
    return nh3.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        attribute_filter=_filter_attribute,
    )


def sanitize_html_markup(text):
    """Jinja filter: sanitized HTML marked safe for output."""
    return Markup(sanitize_html(text))


class _Inventory(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.markup = Counter()
        self.text = []

    def handle_starttag(self, tag, attrs):
        self.markup[('tag', tag)] += 1
        for name, value in attrs:
            self.markup[('attr', tag, name, value or '')] += 1

    def handle_data(self, data):
        self.text.append(data)


def _inventory(html):
    parser = _Inventory()
    parser.feed(html or '')
    parser.close()
    return parser.markup, ' '.join(''.join(parser.text).split())


def has_visible_content(html):
    """True if `html` has non-whitespace text or an image with a source."""
    markup, text = _inventory(html)
    return bool(text) or any(key[:3] == ('attr', 'img', 'src') and key[3] for key in markup)


def removed_content(submitted, cleaned):
    """True if sanitizing `submitted` into `cleaned` dropped text or markup.

    Additions (such as the rel attribute nh3 puts on links) and the benign
    CKEditor image wrappers above are not counted.
    """
    before, before_text = _inventory(submitted)
    after, after_text = _inventory(cleaned)
    if before_text != after_text:
        return True
    for key in before - after:
        if key[0] == 'tag' and key[1] in _BENIGN_TAGS:
            continue
        if key[0] == 'attr' and (key[1], key[2]) in _BENIGN_ATTRIBUTES:
            continue
        return True
    return False
