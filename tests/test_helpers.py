from datetime import datetime

from flask_app.film_helpers import fmt_dt_est


def test_fmt_dt_est_none():
    assert fmt_dt_est(None) == ''


def test_fmt_dt_est_utc_to_est():
    # 2024-01-15 18:00:00 UTC → 13:00 EST (UTC-5 in January)
    dt = datetime(2024, 1, 15, 18, 0, 0)
    result = fmt_dt_est(dt)
    assert result == 'Jan 15, 2024 01:00 PM'


def test_fmt_dt_est_utc_to_edt():
    # 2024-07-04 20:00:00 UTC → 16:00 EDT (UTC-4 in July)
    dt = datetime(2024, 7, 4, 20, 0, 0)
    result = fmt_dt_est(dt)
    assert result == 'Jul 04, 2024 04:00 PM'


def test_fmt_dt_est_midnight():
    dt = datetime(2024, 3, 1, 5, 0, 0)  # 05:00 UTC = 00:00 EST
    result = fmt_dt_est(dt)
    assert result == 'Mar 01, 2024 12:00 AM'
