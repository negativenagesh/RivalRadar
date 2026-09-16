from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from app.connectors.social_feed import (
    _PAST_WINDOW_STOP,
    SocialFeedConnector,
    _order_targets_for_engine,
)
from app.connectors.social_profile.targets import ProfileTarget
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


def test_order_targets_prioritizes_http_oss_on_obscura(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.connectors.social_feed.browser_engine",
        lambda: "obscura",
    )
    targets = [
        ProfileTarget(
            handle="pixisai", platform="linkedin", url="https://linkedin.com/company/pixisai"
        ),
        ProfileTarget(handle="pixis", platform="instagram", url="https://instagram.com/pixis"),
        ProfileTarget(handle="pixisai", platform="x", url="https://x.com/pixisai"),
    ]
    ordered = _order_targets_for_engine(targets)
    assert [t.platform for t in ordered] == ["instagram", "x", "linkedin"]


def test_order_targets_unchanged_on_chromium(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.connectors.social_feed.browser_engine",
        lambda: "chromium",
    )
    targets = [
        ProfileTarget(handle="a", platform="linkedin", url="https://linkedin.com/company/a"),
        ProfileTarget(handle="b", platform="instagram", url="https://instagram.com/b"),
    ]
    assert _order_targets_for_engine(targets) == targets


@pytest.mark.asyncio
async def test_linkedin_tries_oss_then_fresh_browser_on_obscura(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.connectors.social_feed.browser_engine",
        lambda: "obscura",
    )
    window = DateWindow(date_from=date(2026, 9, 14), date_to=date(2026, 9, 16))
    target = ProfileTarget(
        handle="pixisai",
        platform="linkedin",
        url="https://www.linkedin.com/company/pixisai",
    )
    c = SocialFeedConnector(run_id="t", targets=[target], window=window)

    class _FakePage:
        async def goto(self, *_a: object, **_k: object) -> None:
            return None

    class _FakeSession:
        page = _FakePage()
        recorded_video_path = None

        async def __aenter__(self) -> _FakeSession:
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

    monkeypatch.setattr(
        "app.connectors.social_feed.BrowserSession",
        lambda **_k: _FakeSession(),
    )
    monkeypatch.setattr(
        "app.connectors.social_feed.await_or_abandon",
        AsyncMock(side_effect=TimeoutError("timed out after 25s")),
    )
    c._browser_fallback = AsyncMock()  # type: ignore[method-assign]
    c._emit = AsyncMock()  # type: ignore[method-assign]
    c._commit_oss_posts = AsyncMock()  # type: ignore[method-assign]

    await c._scout_linkedin(target, record=False)

    c._browser_fallback.assert_awaited_once()
    details = [
        str(call.args[1].get("detail", ""))
        for call in c._emit.await_args_list
        if call.args and call.args[0] == "action"
    ]
    assert any("oss_try platform=linkedin" in d for d in details)
    assert any("timed out after" in d for d in details)
    assert not any("obscura_skip_linkedin_scraper" in d for d in details)
