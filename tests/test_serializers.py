"""T11: the shared comment JSON shapes keep the keys the player page reads."""
from datetime import datetime
from types import SimpleNamespace

from flask_app import serializers as s


def comment(**over):
    fields = dict(id=7, author_name='a', content='c', comment_type='Comment', timestamp=12,
                  parent_id=None, private_to=None, created_at=datetime(2026, 1, 2, 15, 4))
    fields.update(over)
    return SimpleNamespace(**fields)


def test_thread_comment_keys_and_empty_replies():
    data = s.thread_comment(comment(), True)
    assert set(data) == {'id', 'author_name', 'is_leadership', 'content', 'comment_type',
                         'timestamp', 'created_at', 'private_to', 'replies'}
    assert data['replies'] == [] and data['is_leadership'] is True
    assert data['created_at'] == 'Jan 02, 2026 10:04 AM'


def test_thread_reply_has_no_type_timestamp_or_parent():
    assert set(s.thread_reply(comment(), False)) == {
        'id', 'author_name', 'is_leadership', 'content', 'created_at', 'private_to'}


def test_written_comment_create_has_leadership_update_does_not():
    created = s.written_comment(comment(), False)
    updated = s.written_comment(comment())
    assert set(created) - set(updated) == {'is_leadership'}
    assert set(updated) == {'id', 'author_name', 'content', 'comment_type', 'timestamp',
                            'created_at', 'parent_id', 'private_to'}


def test_private_to_decoding_fails_closed_for_the_client():
    assert s.stored_private_to(None) is None
    assert s.stored_private_to('') is None
    assert s.stored_private_to('["x","y"]') == ['x', 'y']
    assert s.stored_private_to('not json') == []
    assert all(s.stored_private_to(raw) == [] for raw in ('"alice"', '5', '{"a": 1}', 'null'))


def test_iso_and_est_formatting_of_missing_dates():
    assert s.iso_utc(None) == '' and s.fmt_dt_est(None) == ''
    assert s.iso_utc(datetime(2026, 1, 2, 3, 4, 5)) == '2026-01-02T03:04:05Z'
