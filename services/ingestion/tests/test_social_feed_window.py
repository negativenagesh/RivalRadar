from __future__ import annotations

from datetime import UTC, date, datetime

from app.connectors.social_feed import _PAST_WINDOW_STOP, SocialFeedConnector
from app.date_window import DateWindow


def _connector(window: DateWindow) -> SocialFeedConnector:
    return SocialFeedConnector(run_id="test", targets=[], window=window)


def test_skip_outside_outcome_marks_older_than_lookback() -> None:
    window = DateWindow(date_from=date(2026, 9, 12), date_to=date(2026, 9, 14))
    c = _connector(window)
    assert c._skip_outside_outcome(datetime(2026, 9, 11, 14, 0, tzinfo=UTC)) == "older"
    assert c._skip_outside_outcome(datetime(2026, 9, 15, 1, 0, tzinfo=UTC)) == "outside"


def test_default_lookback_includes_recent_linkedin_urn_day() -> None:
    """Sep 11 activity should land in a 7-day lookback ending Sep 14."""
    window = DateWindow.from_lookback(7, now=datetime(2026, 9, 14, 12, 0, tzinfo=UTC))
    assert window.date_from == date(2026, 9, 8)
    assert window.date_to == date(2026, 9, 14)
    posted = datetime(2026, 9, 11, 14, 36, 16, tzinfo=UTC)
    assert window.contains(posted)
    assert _PAST_WINDOW_STOP >= 2
