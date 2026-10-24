"""Shared read-visibility policy for film games, comments, and notifications.

Baseline rules (T03 slice 1). Leadership policy Q1 is still open, so this module
neither adds nor removes leadership exceptions; see docs/visibility-policy.md.

- Games: a hidden game exists only for admins. Everyone else gets the same 404
  as for a game id that does not exist.
- Comments: SQL NULL ``private_to`` is public to anyone who can view the game.
  Any other value is private: visible to the author and the explicitly listed
  recipients only. ``[]`` and malformed values mean author-only (fail closed).
- Replies inherit their ancestors' audience: a reply is visible only when every
  comment in its parent chain is visible too, and its own ``private_to`` (if
  set) also admits the viewer.
- Admins follow the same comment rules; they are not implicit recipients.
"""
import json

from flask import abort

from . import db
from .models import Comment, Game, User


def can_view_game(user, game):
    if user is None or game is None:
        return False
    return not game.is_hidden or bool(user.is_admin)


def get_visible_game_or_404(game_id, user):
    """Return the game, or abort with the same 404 used for missing games."""
    game = db.session.get(Game, game_id)
    if not can_view_game(user, game):
        abort(404)
    return game


def visible_games_query(user):
    query = Game.query
    if not (user and user.is_admin):
        query = query.filter(Game.is_hidden.is_(False))
    return query


def private_recipients(comment):
    """None for a public comment, else the set of explicit recipient usernames."""
    if comment.private_to is None:
        return None
    try:
        recipients = json.loads(comment.private_to)
    except (TypeError, ValueError):
        return set()
    if not isinstance(recipients, list):
        return set()
    return {name for name in recipients if isinstance(name, str)}


def _leadership_exception(user, comment, recipients):
    # Pre-existing rule kept unchanged pending Q1: leadership viewers may read a
    # leadership-authored private comment addressed to at least one person.
    if not (recipients and user.is_leadership):
        return False
    author = User.query.filter_by(username=comment.author_name).first()
    return bool(author and author.is_leadership)


def _admits(user, comment, leadership_exception):
    recipients = private_recipients(comment)
    if recipients is None:
        return True
    if user.username == comment.author_name or user.username in recipients:
        return True
    return leadership_exception and _leadership_exception(user, comment, recipients)


def can_view_comment(user, comment, *, leadership_exception=False):
    """Whether ``user`` may receive this comment's body or any snippet of it.

    ``leadership_exception`` is only enabled by the main film comments API,
    which already applied it before T03 (pending Q1). All other surfaces use
    the explicit author/recipient baseline.
    """
    if user is None or comment is None:
        return False
    if not can_view_game(user, comment.game):
        return False
    seen = set()
    current = comment
    while current is not None:
        if current.id in seen or not _admits(user, current, leadership_exception):
            return False
        seen.add(current.id)
        if current.parent_id is None:
            return True
        current = db.session.get(Comment, current.parent_id)
    # Parent row is missing: fail closed.
    return False
