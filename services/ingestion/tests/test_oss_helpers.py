"""Unit tests for OSS helpers + date filters (no live network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.connectors.oss.common import (
    gallery_dl_date,
    handle_from_url,
    instaloader_post_filter,
    username_from_target,
    ytdlp_yyyymmdd,
)
from app.connectors.oss.linkedin import _parse_relative_date
from app.connectors.oss.netscape import cookie_value, write_netscape_cookies
from app.date_window import DateWindow


def test_date_helpers_match_tool_flags() -> None:
    window = DateWindow(date_from=date(2026, 1, 1), date_to=date(2026, 3, 1))
    assert ytdlp_yyyymmdd(window.date_from) == "20260101"
    assert ytdlp_yyyymmdd(window.date_to) == "20260301"
    assert gallery_dl_date(window.date_from) == "2026-01-01"
    filt = instaloader_post_filter(window)
    assert "datetime(2026, 1, 1)" in filt
    assert "datetime(2026, 3, 2)" in filt  # exclusive end = day after date_to


def test_netscape_cookie_file(tmp_path: Path) -> None:
    path = write_netscape_cookies(
        tmp_path / "cookies.txt",
        [
            {
                "name": "auth_token",
                "value": "abc",
                "domain": ".x.com",
                "path": "/",
                "secure": True,
            },
            {"name": "li_at", "value": "tok", "domain": ".linkedin.com", "path": "/"},
        ],
    )
    text = path.read_text(encoding="utf-8")
    assert "auth_token" in text
    assert "li_at" in text
    assert cookie_value(
        [{"name": "li_at", "value": "tok", "domain": ".linkedin.com"}], "li_at"
    ) == "tok"


def test_username_and_handle_parsing() -> None:
    assert username_from_target("@pixis_ai", "https://www.instagram.com/pixis_ai/") == "pixis_ai"
    assert handle_from_url("https://www.linkedin.com/company/pixisai/posts") == "@pixisai"
    assert username_from_target("", "https://x.com/Pixis_AI") == "Pixis_AI"


def test_linkedin_relative_dates() -> None:
    assert _parse_relative_date("2h") is not None
    assert _parse_relative_date("3d") is not None
    assert _parse_relative_date("just now") is not None
    assert _parse_relative_date("") is None
