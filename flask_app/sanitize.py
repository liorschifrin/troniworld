"""Allowlist sanitizer for article HTML (T05 slice 2).

The allowed markup is what the CKEditor 5 classic build produces by default.
Everything else (scripts, styles, tables, embeds, event handlers, class/style/id
attributes, javascript:/data: URLs) is removed. Stored content is never
rewritten by a migration; existing rows are sanitized when rendered.
"""
import nh3
from markupsafe import Markup

ALLOWED_TAGS = {
    'p', 'h1', 'h2', 'h3', 'strong', 'em', 'u', 's',
    'ul', 'ol', 'li', 'a', 'blockquote', 'br', 'img',
}
ALLOWED_ATTRIBUTES = {'a': {'href'}, 'img': {'src', 'alt'}}
ALLOWED_URL_SCHEMES = {'http', 'https', 'mailto'}
UPLOAD_PREFIX = '/static/uploads/'


def _filter_attribute(tag, attribute, value):
    if tag == 'img' and attribute == 'src':
        if not value.startswith(UPLOAD_PREFIX):
            return None
        if '..' in value or '\\' in value or any(ord(c) < 32 for c in value):
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
