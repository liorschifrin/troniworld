"""JSON shapes shared by the film comment routes.

The response keys are a client contract (``game_player.html``); this module only
removes the copies of the parsing and formatting that built them.
"""
import json
from datetime import timezone
from zoneinfo import ZoneInfo

_EST = ZoneInfo('America/New_York')


def fmt_dt_est(dt):
    """Format a naive-UTC datetime as a human-readable EST/EDT string."""
    if dt is None:
        return ''
    aware = dt.replace(tzinfo=timezone.utc).astimezone(_EST)
    return aware.strftime('%b %d, %Y %I:%M %p')


def iso_utc(dt):
    """ISO string with a trailing Z for a naive-UTC datetime, '' when absent."""
    return dt.isoformat() + 'Z' if dt else ''


def stored_private_to(raw):
    """Decode a ``Comment.private_to`` column: None when public, [] when malformed or not a list.

    Audience decisions use ``visibility.private_recipients``; this only shapes the
    list sent to the client.
    """
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except (ValueError, TypeError, RecursionError):
        return []
    return value if isinstance(value, list) else []


def comment_summary(comment, private_to):
    """Fields every comment response carries."""
    return {
        'id': comment.id,
        'author_name': comment.author_name,
        'content': comment.content,
        'created_at': fmt_dt_est(comment.created_at),
        'private_to': private_to,
    }


def thread_comment(comment, is_leadership):
    """A top-level comment in the thread listing (replies are appended by the caller)."""
    data = comment_summary(comment, stored_private_to(comment.private_to))
    data.update(is_leadership=bool(is_leadership), comment_type=comment.comment_type,
                timestamp=comment.timestamp, replies=[])
    return data


def thread_reply(reply, is_leadership):
    data = comment_summary(reply, stored_private_to(reply.private_to))
    data['is_leadership'] = bool(is_leadership)
    return data


def written_comment(comment, is_leadership=None):
    """The comment echoed back by create (with ``is_leadership``) and update (without)."""
    data = comment_summary(comment, stored_private_to(comment.private_to))
    data.update(comment_type=comment.comment_type, timestamp=comment.timestamp,
                parent_id=comment.parent_id)
    if is_leadership is not None:
        data['is_leadership'] = bool(is_leadership)
    return data
