"""Inclusive date window for scout lookback / custom from–to."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta


class DateWindowError(ValueError):
    pass


@dataclass(frozen=True)
class DateWindow:
    date_from: date
    date_to: date

    @classmethod
    def from_lookback(cls, days: int, *, now: datetime | None = None) -> DateWindow:
        if days < 1 or days > 90:
            raise DateWindowError("lookback_days must be between 1 and 90")
        now = now or datetime.now(UTC)
        end = now.date()
        start = (now - timedelta(days=days - 1)).date()
        return cls(date_from=start, date_to=end)

    @classmethod
    def resolve(
        cls,
        *,
        lookback_days: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        now: datetime | None = None,
    ) -> DateWindow:
        if date_from is not None or date_to is not None:
            if date_from is None or date_to is None:
                raise DateWindowError("Both date_from and date_to are required for a custom range")
            if date_from > date_to:
                raise DateWindowError("date_from must be on or before date_to")
            span = (date_to - date_from).days + 1
            if span > 90:
                raise DateWindowError("Custom date range cannot exceed 90 days")
            return cls(date_from=date_from, date_to=date_to)
        days = lookback_days if lookback_days is not None else 7
        return cls.from_lookback(days, now=now)

    def contains(self, dt: datetime) -> bool:
        d = dt.astimezone(UTC).date() if dt.tzinfo else dt.replace(tzinfo=UTC).date()
        return self.date_from <= d <= self.date_to

    @property
    def span_days(self) -> int:
        return (self.date_to - self.date_from).days + 1

    def cutoff_datetime(self) -> datetime:
        """Start of date_from in UTC (for connectors that filter by timestamp)."""
        return datetime(self.date_from.year, self.date_from.month, self.date_from.day, tzinfo=UTC)
