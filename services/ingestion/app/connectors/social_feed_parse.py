"""Platform-aware helpers: collect post URLs and parse metrics from a post page."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import UTC, datetime
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
    r"(?P<num>[\d,.]+)\s*(?P<suffix>[KkMmBb])?\s*(?P<label>likes?|comments?|views?|shares?|reposts?|reactions?|retweets?|replies)",
    re.I,
)

_NAV_DESTROY = ("execution context was destroyed", "most likely because of a navigation", "frame was detached")
_TWITTER_EPOCH_MS = 1_288_834_974_657


_LI_ACTIVITY_RE = re.compile(
    r"(?:urn:li:activity:|activity[:-]|/feed/update/urn:li:activity:)(\d{15,})"
)


def posted_at_from_linkedin_activity(raw: str) -> datetime | None:
    """LinkedIn activity IDs encode Unix ms in the high bits (id >> 22)."""
    if not raw:
        return None
    match = _LI_ACTIVITY_RE.search(raw) or re.search(r"(\d{18,})", raw)
    if not match:
        return None
    try:
        activity_id = int(match.group(1))
    except (TypeError, ValueError):
        return None
    ts_ms = activity_id >> 22
    if ts_ms < 1_500_000_000_000 or ts_ms > 2_200_000_000_000:
        return None
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    if dt.year < 2018 or dt.year > 2035:
        return None
    return dt


def posted_at_from_url(platform: str, url: str) -> datetime | None:
    """Derive a real timestamp from a post URL when the page hid <time datetime>.

    X status IDs are Twitter snowflakes. LinkedIn activity URNs encode Unix ms.
    Instagram shortcodes are not a reliable clock — those stay page-parsed only.
    """
    platform = normalize_platform(platform)
    if platform == "linkedin":
        return posted_at_from_linkedin_activity(url)
    if platform not in {"x", "twitter"}:
        return None
    match = re.search(r"/status/(\d+)", url)
    if not match:
        return None
    status_id = int(match.group(1))
    if status_id < 1_000_000_000_000:
        return None
    ms = (status_id >> 22) + _TWITTER_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=UTC)


def normalize_platform(platform: str) -> str:
    p = (platform or "web").lower()
    if p == "twitter":
        return "x"
    return p


def parse_count(raw: str | None) -> int:
    if not raw:
        return 0
    text = raw.strip().replace(",", "").replace(" ", "")
    if not text or not any(ch.isdigit() for ch in text):
        return 0
    m = re.match(r"^([\d.]+)([KkMmBb])?$", text)
    if not m:
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0
    num = m.group(1).strip(".")
    if not num:
        return 0
    try:
        value = float(num)
    except ValueError:
        return 0
    suffix = (m.group(2) or "").upper()
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
    return int(value * mult)


def canonicalize_post_url(platform: str, url: str) -> str:
    """Collapse photo/analytics/query variants to the canonical post URL."""
    platform = normalize_platform(platform)
    parsed = urlparse(url.split("?")[0].split("#")[0])
    path = parsed.path or ""
    if platform in {"x", "twitter"}:
        m = re.search(r"/status/(\d+)", path)
        if m:
            user = "i"
            um = re.match(r"/([^/]+)/status/", path)
            if um and um.group(1) not in {"i", "intent"}:
                user = um.group(1)
            return f"https://x.com/{user}/status/{m.group(1)}"
    if platform == "instagram":
        m = re.search(r"/(p|reel|tv)/([A-Za-z0-9_-]+)", path)
        if m:
            return f"https://www.instagram.com/{m.group(1)}/{m.group(2)}/"
    scheme = parsed.scheme or "https"
    netloc = parsed.netloc
    if netloc:
        return f"{scheme}://{netloc}{path.rstrip('/')}"
    return url.split("?")[0].split("#")[0]


def absolutize(base: str, href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return urljoin(base, href)


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
            abs_url = canonicalize_post_url(platform, absolutize(base, clean))
            path = urlparse(abs_url).path
            if pattern and not pattern.search(path) and not pattern.search(abs_url):
                continue
            if platform == "instagram" and "/p/" not in abs_url and "/reel/" not in abs_url and "/tv/" not in abs_url:
                continue
            if (
                platform == "linkedin"
                and "recent-activity" in abs_url
                and "/posts/" not in abs_url
                and "activity" not in abs_url
            ):
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


async def parse_post_page(
    page: Page,
    *,
    platform: str,
    post_url: str,
    skip_time_wait: bool = False,
) -> dict[str, Any]:
    """Extract caption, media URL, metrics, posted_at from an open post page."""
    platform = normalize_platform(platform)
    if platform in {"instagram", "x"} and not skip_time_wait:
        with contextlib.suppress(Exception):
            await page.wait_for_selector("time[datetime], time", timeout=1200)
    try:
        data = await safe_evaluate(
            page,
            """() => {
              const meta = (prop) => {
                const el = document.querySelector(`meta[property="${prop}"], meta[name="${prop}"]`);
                return el ? el.getAttribute('content') : null;
              };
              const timeDatetimes = Array.from(document.querySelectorAll('time[datetime]'))
                .map(el => el.getAttribute('datetime'))
                .filter(Boolean)
                .slice(0, 8);
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
              const likeBtn = document.querySelector('[data-testid="like"], [data-testid="unlike"]');
              const replyBtn = document.querySelector('[data-testid="reply"]');
              const rtBtn = document.querySelector('[data-testid="retweet"]');
              let takenAtUnix = null;
              let jsonLdDate = null;
              try {
                const html = document.documentElement.innerHTML;
                const taken = html.match(/"taken_at(?:_timestamp)?"\\s*:\\s*([0-9]{10})/);
                if (taken) takenAtUnix = Number(taken[1]);
                const ld = document.querySelector('script[type="application/ld+json"]');
                if (ld && ld.textContent) {
                  const parsed = JSON.parse(ld.textContent);
                  const node = Array.isArray(parsed) ? parsed[0] : parsed;
                  jsonLdDate = (node && (node.datePublished || node.uploadDate || node.dateCreated)) || null;
                }
              } catch (e) {}
              return {
                ogTitle: meta('og:title'),
                ogDesc: meta('og:description'),
                ogImage: meta('og:image'),
                ogVideo: meta('og:video') || meta('og:video:secure_url'),
                published: meta('article:published_time') || meta('og:updated_time')
                  || (timeDatetimes[0] || null),
                timeDatetimes,
                takenAtUnix,
                jsonLdDate,
                bodyText,
                imgCandidates,
                videoSrc,
                aria,
                likeAria: likeBtn ? likeBtn.getAttribute('aria-label') : null,
                replyAria: replyBtn ? replyBtn.getAttribute('aria-label') : null,
                rtAria: rtBtn ? rtBtn.getAttribute('aria-label') : null,
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
        elif label.startswith("share") or label.startswith("repost") or label.startswith("retweet"):
            shares = max(shares, n)

    extra_labels = list(data.get("aria") or [])
    for key in ("likeAria", "replyAria", "rtAria"):
        val = data.get(key)
        if isinstance(val, str):
            extra_labels.append(val)
    for label in extra_labels:
        if not isinstance(label, str):
            continue
        for match in _COUNT_RE.finditer(label):
            n = parse_count(match.group("num") + (match.group("suffix") or ""))
            kind = match.group("label").lower()
            if kind.startswith("like") or kind.startswith("reaction"):
                likes = max(likes, n)
            elif kind.startswith("comment") or kind.startswith("repl"):
                comments = max(comments, n)
            elif kind.startswith("view"):
                views = max(views, n)
            elif kind.startswith("share") or kind.startswith("repost") or kind.startswith("retweet"):
                shares = max(shares, n)

    caption = (data.get("ogDesc") or data.get("ogTitle") or "").strip()
    title = str(data.get("title") or "").strip()
    if not caption:
        caption = title
    if platform == "instagram" and " on Instagram:" in caption:
        caption = caption.split(" on Instagram:", 1)[-1].strip().strip("“\"'")
    low = caption.lower()
    if (
        "sign up" in low
        and "linkedin" in low
        or low.endswith("instagram photos and videos")
        or low in {"linkedin", "x", "instagram"}
    ):
        caption = ""

    media_url = data.get("ogImage") or data.get("videoSrc") or data.get("ogVideo")
    imgs = data.get("imgCandidates") or []
    if not media_url and isinstance(imgs, list) and imgs:
        media_url = max((str(u) for u in imgs if isinstance(u, str)), key=len, default=None)

    posted_at = _parse_iso(data.get("published"))
    if posted_at is None:
        for stamp in data.get("timeDatetimes") or []:
            posted_at = _parse_iso(stamp)
            if posted_at:
                break
    if posted_at is None:
        posted_at = _parse_iso(data.get("jsonLdDate"))
    if posted_at is None:
        unix = data.get("takenAtUnix")
        if isinstance(unix, (int, float)) and unix > 1_000_000_000:
            posted_at = datetime.fromtimestamp(float(unix), tz=UTC)
    if posted_at is None:
        posted_at = posted_at_from_url(platform, post_url)
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
