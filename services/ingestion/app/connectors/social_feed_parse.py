"""Platform-aware helpers: collect post URLs and parse metrics from a post page."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Profile → post link patterns per platform
_POST_HREF: dict[str, re.Pattern[str]] = {
    "instagram": re.compile(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?"),
    "threads": re.compile(r"/(@[^/]+/post/[A-Za-z0-9_-]+|t/[A-Za-z0-9_-]+)"),
    "tiktok": re.compile(r"/video/(\d+)"),
    "x": re.compile(r"/status/(\d+)"),
    "twitter": re.compile(r"/status/(\d+)"),
    "linkedin": re.compile(
        r"(?:/posts/[^/?#]+|/feed/update/[^/?#]+|/pulse/[^/?#]+|"
        r"urn:li:activity:\d+|activity[:-]\d+|recent-activity/all)"
    ),
}

_COUNT_RE = re.compile(
    r"(?P<num>[\d,.]+)\s*(?P<suffix>[KkMmBb])?\s*(?P<label>likes?|comments?|views?|shares?|reposts?|reactions?)",
    re.I,
)

_NAV_DESTROY = ("execution context was destroyed", "most likely because of a navigation", "frame was detached")


def normalize_platform(platform: str) -> str:
    p = (platform or "web").lower()
    if p == "twitter":
        return "x"
    return p


def parse_count(raw: str | None) -> int:
    if not raw:
        return 0
    text = raw.strip().replace(",", "").replace(" ", "")
    m = re.match(r"^([\d.]+)([KkMmBb])?$", text)
    if not m:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0
    value = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return int(value * mult)


def absolutize(base: str, href: str) -> str:
    return urljoin(base if base.endswith("/") else base + "/", href)


def _is_nav_destroy(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in _NAV_DESTROY)


async def settle_page(
    page: Page,
    *,
    quiet_ms: int = 300,
    wait_network: bool = False,
) -> None:
    """Wait out SPA redirects so evaluate won't hit a dying document."""
    with contextlib.suppress(Exception):
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    if wait_network:
        with contextlib.suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=1200)
    with contextlib.suppress(Exception):
        await page.wait_for_timeout(quiet_ms)


async def _timed_evaluate(page: Page, expression: str, *, timeout_ms: int = 10000) -> Any:
    """page.evaluate has no timeout kwarg — bound it via default timeout + asyncio."""
    page.set_default_timeout(timeout_ms)
    try:
        return await asyncio.wait_for(page.evaluate(expression), timeout=(timeout_ms / 1000) + 2)
    finally:
        page.set_default_timeout(30000)


async def safe_evaluate(page: Page, expression: str, *, retries: int = 2, timeout_ms: int = 10000) -> Any:
    last: BaseException | None = None
    for attempt in range(retries):
        try:
            await settle_page(page, quiet_ms=200 if attempt else 300)
            return await _timed_evaluate(page, expression, timeout_ms=timeout_ms)
        except Exception as exc:  # noqa: BLE001
            last = exc
            if _is_nav_destroy(exc) and attempt + 1 < retries:
                logger.info("evaluate retry after navigation (%s/%s)", attempt + 1, retries)
                continue
            raise
    if last:
        raise last
    return None


async def _collect_hrefs(page: Page) -> list[str]:
    """Fast href scrape — capped DOM walk (never locator.evaluate_all on huge trees)."""
    script = """() => {
      const out = [];
      const seen = new Set();
      const push = (h) => {
        if (!h || seen.has(h)) return;
        seen.add(h);
        out.push(h);
      };
      const anchors = document.querySelectorAll('a[href]');
      const n = Math.min(anchors.length, 600);
      for (let i = 0; i < n; i++) push(anchors[i].getAttribute('href'));
      // LinkedIn activity cards often expose urns without clean /posts/ hrefs
      document.querySelectorAll('[data-urn*="activity"], [data-id*="activity"]').forEach((el) => {
        const urn = el.getAttribute('data-urn') || el.getAttribute('data-id');
        if (urn && urn.includes('activity')) {
          push('https://www.linkedin.com/feed/update/' + urn);
        }
      });
      return out;
    }"""
    for attempt in range(2):
        try:
            await settle_page(page, quiet_ms=150 if attempt else 250)
            hrefs = await _timed_evaluate(page, script, timeout_ms=8000)
            return [h for h in (hrefs or []) if isinstance(h, str)]
        except Exception as exc:  # noqa: BLE001
            if _is_nav_destroy(exc) and attempt + 1 < 2:
                logger.info("href collect retry after navigation")
                continue
            logger.warning("href collect failed: %s", exc)
            return []
    return []


async def collect_post_urls(
    page: Page,
    *,
    platform: str,
    profile_url: str,
    limit: int = 20,
    max_scrolls: int = 4,
) -> list[str]:
    """Scroll a profile and collect unique post/detail URLs."""
    platform = normalize_platform(platform)
    pattern = _POST_HREF.get(platform)
    found: list[str] = []
    seen: set[str] = set()
    base = page.url or profile_url

    for scroll_i in range(max_scrolls):
        hrefs = await _collect_hrefs(page)
        for href in hrefs:
            clean = href.split("?")[0].split("#")[0]
            abs_url = absolutize(base, clean)
            path = urlparse(abs_url).path
            if pattern and not pattern.search(path) and not pattern.search(abs_url):
                continue
            if platform == "instagram" and "/p/" not in abs_url and "/reel/" not in abs_url and "/tv/" not in abs_url:
                continue
            if platform == "linkedin":
                # Prefer concrete post/update URLs over "recent-activity" listing pages
                if "recent-activity" in abs_url and "/posts/" not in abs_url and "activity" not in abs_url:
                    continue
            if abs_url in seen:
                continue
            seen.add(abs_url)
            found.append(abs_url)
            if len(found) >= limit:
                return found
        if scroll_i + 1 >= max_scrolls:
            break
        try:
            await page.mouse.wheel(0, 1600)
            await page.wait_for_timeout(500)
            base = page.url or base
        except Exception as exc:  # noqa: BLE001
            if _is_nav_destroy(exc):
                await settle_page(page, quiet_ms=200)
                base = page.url or base
                continue
            logger.warning("scroll failed during collect: %s", exc)
            break
    return found


async def parse_post_page(page: Page, *, platform: str, post_url: str) -> dict[str, Any]:
    """Extract caption, media URL, metrics, posted_at from an open post page."""
    platform = normalize_platform(platform)
    try:
        data = await safe_evaluate(
            page,
            """() => {
              const meta = (prop) => {
                const el = document.querySelector(`meta[property="${prop}"], meta[name="${prop}"]`);
                return el ? el.getAttribute('content') : null;
              };
              const timeEl = document.querySelector('time[datetime]');
              const bodyText = document.body ? document.body.innerText.slice(0, 20000) : '';
              const imgCandidates = Array.from(document.querySelectorAll('article img, main img, img'))
                .map(img => img.currentSrc || img.src)
                .filter(src => src && !src.includes('data:') && src.startsWith('http'));
              const video = document.querySelector('video');
              const videoSrc = video ? (video.currentSrc || video.getAttribute('poster') || null) : null;
              const aria = Array.from(document.querySelectorAll('[aria-label]'))
                .map(e => e.getAttribute('aria-label'))
                .filter(Boolean)
                .slice(0, 80);
              return {
                ogTitle: meta('og:title'),
                ogDesc: meta('og:description'),
                ogImage: meta('og:image'),
                ogVideo: meta('og:video') || meta('og:video:secure_url'),
                published: meta('article:published_time') || meta('og:updated_time')
                  || (timeEl ? timeEl.getAttribute('datetime') : null),
                bodyText,
                imgCandidates,
                videoSrc,
                aria,
                title: document.title || '',
              };
            }""",
            timeout_ms=12000,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("parse_post_page evaluate failed for %s: %s", post_url, exc)
        data = {"title": "", "bodyText": "", "imgCandidates": [], "aria": []}

    if not isinstance(data, dict):
        data = {}

    likes = comments = views = shares = 0
    body = str(data.get("bodyText") or "")
    for match in _COUNT_RE.finditer(body):
        n = parse_count(match.group("num") + (match.group("suffix") or ""))
        label = match.group("label").lower()
        if label.startswith("like") or label.startswith("reaction"):
            likes = max(likes, n)
        elif label.startswith("comment"):
            comments = max(comments, n)
        elif label.startswith("view"):
            views = max(views, n)
        elif label.startswith("share") or label.startswith("repost"):
            shares = max(shares, n)

    for label in data.get("aria") or []:
        if not isinstance(label, str):
            continue
        for match in _COUNT_RE.finditer(label):
            n = parse_count(match.group("num") + (match.group("suffix") or ""))
            kind = match.group("label").lower()
            if kind.startswith("like") or kind.startswith("reaction"):
                likes = max(likes, n)
            elif kind.startswith("comment"):
                comments = max(comments, n)
            elif kind.startswith("view"):
                views = max(views, n)

    caption = (data.get("ogDesc") or data.get("ogTitle") or data.get("title") or "").strip()
    if platform == "instagram" and " on Instagram:" in caption:
        caption = caption.split(" on Instagram:", 1)[-1].strip().strip("“\"'")

    media_url = data.get("ogImage") or data.get("videoSrc") or data.get("ogVideo")
    imgs = data.get("imgCandidates") or []
    if not media_url and isinstance(imgs, list) and imgs:
        media_url = max((str(u) for u in imgs if isinstance(u, str)), key=len, default=None)

    posted_at = _parse_iso(data.get("published"))
    external_id = external_id_for(platform, post_url)

    return {
        "external_post_id": external_id,
        "caption": caption[:2000] or f"{platform} post",
        "media_url": media_url,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "views": views,
        "posted_at": posted_at,
        "post_url": post_url,
    }


def _parse_iso(raw: Any) -> datetime | None:
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def external_id_for(platform: str, url: str) -> str:
    path = urlparse(url).path
    pattern = _POST_HREF.get(platform)
    if pattern:
        m = pattern.search(url) or pattern.search(path)
        if m:
            token = m.group(1) if m.lastindex else m.group(0)
            token = re.sub(r"[^\w.:-]+", "-", str(token))[:80]
            return f"{platform}:{token}"[:100]
    slug = path.strip("/").replace("/", "-")[-60:] or "post"
    return f"{platform}:{slug}"[:100]
