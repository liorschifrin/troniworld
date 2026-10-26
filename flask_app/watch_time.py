"""Idempotent, bounded watch-time accounting (T09).

Watch time is approximate engagement, never proof of learning. Contract v2: a page
load makes a random ``client_session_id``; every chunk of seconds it reports carries a
unique ``event_id``. The server stores each accepted event, so a retried or replayed
chunk is acknowledged without being counted again, and a chunk that arrives late is
still counted once.

Tabs: the client counts only while the video is playing in the visible, focused tab,
and each tab (page load) owns one session. As a server-side backstop, a chunk that
overlaps seconds already credited to another session of the same user and game is
trimmed, so two tabs left playing cannot add up to more than elapsed time.
"""
import math
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest

from . import db
from .input_validation import timestamp
from .models import VideoWatchEvent, VideoWatchSession

# One chunk may credit at most this many seconds (the client sends about every 10).
MAX_INCREMENT_SECONDS = 60
MAX_ID_LENGTH = 64


def _identifier(value, field, *, required):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID_LENGTH or not value.isprintable():
        raise BadRequest(f'{field} must be a printable string of 1-{MAX_ID_LENGTH} characters')
    return value


def parse_payload(data):
    """Validate a request body; returns (seconds, position, client_session_id, event_id)."""
    if not isinstance(data, dict):
        raise BadRequest('A JSON object is required')
    seconds = data.get('seconds_watched', 0)
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
        raise BadRequest('seconds_watched must be a finite number of 0 or more')
    position = timestamp(data.get('playback_position'), 'playback_position')
    if seconds == 0 and position is None:
        raise BadRequest('Invalid watch duration')
    client_session_id = _identifier(data.get('client_session_id'), 'client_session_id', required=True)
    event_id = _identifier(data.get('event_id'), 'event_id', required=seconds > 0)
    return min(float(seconds), float(MAX_INCREMENT_SECONDS)), position, client_session_id, event_id


def _session_for(user_id, game_id, client_session_id, now):
    query = VideoWatchSession.query.filter_by(
        user_id=user_id, game_id=game_id, client_session_id=client_session_id)
    session = query.first()
    if session is not None:
        return session
    try:
        with db.session.begin_nested():
            session = VideoWatchSession(
                user_id=user_id, game_id=game_id, client_session_id=client_session_id,
                watch_duration_seconds=0, session_start=now, last_updated=now)
            db.session.add(session)
    except IntegrityError:  # a concurrent first chunk made it; use that row
        session = query.one()
    return session


def _overlap_seconds(session, seconds, now):
    """Seconds of this chunk already credited to another session of the same user and game."""
    latest = (db.session.query(func.max(VideoWatchEvent.received_at))
              .join(VideoWatchSession, VideoWatchEvent.session_id == VideoWatchSession.id)
              .filter(VideoWatchSession.user_id == session.user_id,
                      VideoWatchSession.game_id == session.game_id,
                      VideoWatchSession.id != session.id).scalar())
    if latest is None:
        return 0.0
    return max(0.0, min(seconds, (latest - (now - timedelta(seconds=seconds))).total_seconds()))


def record(user_id, game_id, data, now=None):
    """Apply one chunk. Returns (session, credited_seconds, duplicate)."""
    seconds, position, client_session_id, event_id = parse_payload(data)
    now = now or datetime.utcnow()
    session = _session_for(user_id, game_id, client_session_id, now)

    credited, duplicate = 0.0, False
    if event_id is not None:
        duplicate = VideoWatchEvent.query.filter_by(session_id=session.id, event_id=event_id).first() is not None
        if not duplicate:
            credited = max(0.0, seconds - _overlap_seconds(session, seconds, now))
            # A session cannot hold more than the time since it opened plus one chunk.
            elapsed = (now - session.session_start).total_seconds() + MAX_INCREMENT_SECONDS
            total = db.session.query(func.coalesce(func.sum(VideoWatchEvent.seconds_credited), 0.0)).filter(
                VideoWatchEvent.session_id == session.id).scalar()
            credited = max(0.0, min(credited, elapsed - total))
            try:
                with db.session.begin_nested():
                    db.session.add(VideoWatchEvent(session_id=session.id, event_id=event_id,
                                                   seconds_credited=credited, received_at=now))
            except IntegrityError:  # the same event raced in on another worker
                duplicate, credited = True, 0.0
            else:
                session.watch_duration_seconds = int(round(total + credited))
    if position is not None:
        session.last_position_seconds = position
    session.last_updated = now
    db.session.commit()
    return session, credited, duplicate
