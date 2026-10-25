"""Per-session CSRF token checked on every state-changing request."""
import hmac
import json
import secrets

from flask import flash, jsonify, render_template, request, session

SESSION_KEY = 'csrf_token'
FORM_FIELD = 'csrf_token'
HEADER = 'X-CSRFToken'
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'TRACE'})
ERROR = 'CSRF token missing or invalid'

# navigator.sendBeacon cannot set headers, so this endpoint also reads the
# token from its JSON payload. The raw body is parsed here so the handler's
# own content-type handling (the T09 string-beacon defect) is unchanged.
BEACON_ENDPOINTS = frozenset({'track_watch_time'})

# Browser form posts answer with a flashed page; every other write is JSON.
# manage_users also serves an AJAX role toggle, detected by X-Requested-With.
FORM_ENDPOINTS = frozenset({
    'register', 'login', 'logout', 'new_post', 'edit_post', 'delete_post',
    'manage_users', 'create_users_for_all_players', 'new_tournament',
    'new_game', 'edit_game', 'upload_game_csv', 'delete_player_sheet',
})


def csrf_token():
    """Return the session's token, creating it on first use."""
    if SESSION_KEY not in session:
        session[SESSION_KEY] = secrets.token_urlsafe(32)
    return session[SESSION_KEY]


def _submitted_token():
    token = request.headers.get(HEADER) or request.form.get(FORM_FIELD)
    if not token and request.endpoint in BEACON_ENDPOINTS:
        try:
            body = json.loads(request.get_data(cache=True))
        except (ValueError, RecursionError):
            body = None
        if isinstance(body, dict):
            token = body.get(FORM_FIELD)
    return token if isinstance(token, str) else None


def _reject():
    wants_json = (request.endpoint not in FORM_ENDPOINTS
                  or request.headers.get('X-Requested-With') == 'XMLHttpRequest')
    if wants_json:
        return jsonify(error=ERROR), 403
    flash('Your session expired or the form was invalid. Please reload the page and try again.', 'error')
    film = request.path.startswith(('/film', '/admin'))
    template = 'film_room/film_base.html' if film else 'articles/base.html'
    return render_template(template), 403


def check_csrf():
    # Unrouted requests keep their normal 404/405 responses.
    if request.method in SAFE_METHODS or request.routing_exception is not None:
        return None
    expected = session.get(SESSION_KEY)
    submitted = _submitted_token()
    if not expected or not submitted or not hmac.compare_digest(
            expected.encode(), submitted.encode('utf-8', 'replace')):
        return _reject()
    return None


def init_app(app):
    app.before_request(check_csrf)
    app.add_template_global(csrf_token)
