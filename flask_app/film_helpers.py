from datetime import timezone
from zoneinfo import ZoneInfo

_EST = ZoneInfo('America/New_York')

def fmt_dt_est(dt):
    """Format a naive-UTC datetime as a human-readable EST/EDT string."""
    if dt is None:
        return ''
    aware = dt.replace(tzinfo=timezone.utc).astimezone(_EST)
    return aware.strftime('%b %d, %Y %I:%M %p')
