"""LinkedIn company posts via joeyism/linkedin_scraper (Playwright-backed)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Page

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import download_media_to_store
from app.connectors.oss.netscape import cookie_value
from app.connectors.session_cookies import cookies_from_sessions
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


class LinkedInScraperError(RuntimeError):
    pass


def _company_slug(url: str, handle: str) -> str:
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if "company" in parts:
        i = parts.index("company")
        if i + 1 < len(parts):
            return parts[i + 1]
    return handle.lstrip("@").split("/")[0]


def _parse_relative_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip().lower()
    now = datetime.now(UTC)
    # Absolute ISO
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    m = re.match(r"(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks|mo|mon|month|months|y|yr|year|years)\b", text)
    if not m:
        if "just now" in text or text == "now":
            return now
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit.startswith("m") and not unit.startswith("mo"):
        return now - timedelta(minutes=n)
    if unit.startswith("h"):
        return now - timedelta(hours=n)
    if unit.startswith("d"):
        return now - timedelta(days=n)
    if unit.startswith("w"):
        return now - timedelta(weeks=n)
    if unit.startswith("mo"):
        return now - timedelta(days=30 * n)
    if unit.startswith("y"):
        return now - timedelta(days=365 * n)
    return None


async def fetch_linkedin_company_posts(
    *,
    page: Page,
    run_id: str,
    handle: str,
    url: str,
    window: DateWindow,
    platform_sessions: dict[str, Any],
    object_store: ObjectStore | None,
    max_posts: int = 25,
) -> tuple[RawAccount, list[RawPost]]:
    """Use linkedin_scraper's CompanyPostsScraper on an authenticated Playwright page."""
    try:
        from linkedin_scraper import CompanyPostsScraper
    except ImportError as exc:  # pragma: no cover
        raise LinkedInScraperError("linkedin-scraper not installed") from exc

    cookies = cookies_from_sessions(platform_sessions, platforms={"linkedin"})
    if not cookies:
        raise LinkedInScraperError("no linkedin connect cookies")

    # Ensure li_at is present (BrowserSession already injected cookies; reinforce)
    li_at = cookie_value(cookies, "li_at")
    if li_at:
        try:
            from linkedin_scraper import login_with_cookie

            await login_with_cookie(page, li_at)
        except Exception as exc:  # noqa: BLE001
            logger.info("linkedin login_with_cookie soft-fail: %s", exc)

    slug = _company_slug(url, handle)
    company_url = url if "/company/" in url else f"https://www.linkedin.com/company/{slug}"
    scraper = CompanyPostsScraper(page)
    try:
        raw_posts = await scraper.scrape(company_url, limit=max_posts)
    except Exception as exc:  # noqa: BLE001
        raise LinkedInScraperError(f"company posts scrape failed: {exc}") from exc

    account = RawAccount(
        handle=f"@{slug}"[:100],
        display_name=slug.replace("-", " ").title()[:200],
        platform="linkedin",
    )

    posts: list[RawPost] = []
    for item in raw_posts:
        posted = _parse_relative_date(getattr(item, "posted_date", None))
        if posted is None:
            posted = datetime.now(UTC)
            uncertain = True
        else:
            uncertain = False
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=UTC)
            if not window.contains(posted):
                continue

        urn = getattr(item, "urn", None) or ""
        post_url = getattr(item, "linkedin_url", None) or (
            f"https://www.linkedin.com/feed/update/{urn}" if urn else company_url
        )
        external = f"linkedin:{urn or post_url}"[:100]
        external = re.sub(r"[^\w.:-]+", "-", external)[:100]

        image_urls = list(getattr(item, "image_urls", None) or [])
        video_url = getattr(item, "video_url", None)
        media_urls = ([video_url] if video_url else []) + image_urls
        media_keys: list[str] = []
        image_url: str | None = media_urls[0] if media_urls else None

        if object_store and media_urls:
            key = await download_media_to_store(
                object_store,
                run_id=run_id,
                post_id=external,
                url=media_urls[0],
            )
            if key:
                media_keys = [key]
                image_url = f"/ingestion/media/{key}"

        themes = [
            "linkedin",
            "source:linkedin_scraper",
            f"link:{str(post_url)[:180]}",
            f"date_from:{window.date_from.isoformat()}",
            f"date_to:{window.date_to.isoformat()}",
        ]
        if uncertain:
            themes.append("posted_at_uncertain")

        posts.append(
            RawPost(
                account_handle=account["handle"],
                external_post_id=external,
                format="founder_post",
                theme_tags=themes,
                caption=(getattr(item, "text", None) or "")[:2000] or f"LinkedIn {slug}",
                image_url=image_url,
                likes=int(getattr(item, "reactions_count", None) or 0),
                comments=int(getattr(item, "comments_count", None) or 0),
                shares=int(getattr(item, "reposts_count", None) or 0),
                views=0,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
                media_urls=media_urls,
                media_keys=media_keys,
            )
        )

    return account, posts
