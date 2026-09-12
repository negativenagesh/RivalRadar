from datetime import UTC, date, datetime

import pytest
from app.date_window import DateWindow, DateWindowError

UTC = UTC


def test_from_lookback_inclusive_span() -> None:
    now = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
    window = DateWindow.from_lookback(3, now=now)
    assert window.span_days == 3
    assert window.date_to == date(2026, 9, 12)
    assert window.date_from == date(2026, 9, 10)


def test_custom_range_validation() -> None:
    window = DateWindow.resolve(date_from=date(2026, 9, 1), date_to=date(2026, 9, 10))
    assert window.span_days == 10
    with pytest.raises(DateWindowError):
        DateWindow.resolve(date_from=date(2026, 9, 10), date_to=date(2026, 9, 1))


def test_contains() -> None:
    window = DateWindow(date_from=date(2026, 9, 1), date_to=date(2026, 9, 3))
    assert window.contains(datetime(2026, 9, 2, tzinfo=UTC))
    assert not window.contains(datetime(2026, 8, 31, tzinfo=UTC))
