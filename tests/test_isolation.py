"""Fail closed if configuration drifts away from disposable storage."""
import pytest

from conftest import assert_isolated


def test_database_override_guard(app, tmp_path, monkeypatch):
    with monkeypatch.context() as change:
        change.setitem(app.config, 'SQLALCHEMY_DATABASE_URI', 'sqlite:///forbidden.db')
        with pytest.raises(AssertionError):
            assert_isolated(tmp_path)
    assert_isolated(tmp_path)


def test_upload_override_guard(app, tmp_path, monkeypatch):
    with monkeypatch.context() as change:
        change.setitem(app.config, 'UPLOAD_FOLDER', str(tmp_path.parent / 'forbidden'))
        with pytest.raises(AssertionError):
            assert_isolated(tmp_path)
    assert_isolated(tmp_path)
