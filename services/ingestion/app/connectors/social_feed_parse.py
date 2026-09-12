"""Platform-aware helpers: collect post URLs and parse metrics from a post page."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page

# Profile → post link patterns per platform
_POST_HREF: dict[str, re.Pattern[str]] = {
    "instagram": re.compile(r"/(?:p|reel|tv)/([A-Za-z0-9_-]+)/?"),
    "threads": re.compile(r"/(@[^/]+/post/[A-Za-z0-9_-]+|t/[A-Za-z0-9_-]+)"),
    "tiktok": re.compile(r"/video/(\d+)"),
    "x": re.compile(r"/status/(\d+)"),
    "twitter": re.compile(r"/status/(\d+)"),
    "linkedin": re.compile(r"/(?:posts|feed/update|pulse)/([^/?#]+)"),
}

_COUNT_RE = re.compile(
    r"(?P<num>[\d,.]+)\s*(?P<suffix>[KkMmBb])?\s*(?P<label>likes?|comments?|views?|shares?|reposts?|reactions?)",
    re.I,
)


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


async def collect_post_urls(page: Page, *, platform: str, profile_url: str, limit: int = 40) -> list[str]:
    """Scroll a profile and collect unique post/detail URLs."""
    platform = normalize_platform(platform)
    pattern = _POST_HREF.get(platform)
    found: list[str] = []
    seen: set[str] = set()

    for _ in range(6):
        hrefs = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => e.getAttribute('href')).filter(Boolean)",
        )
        for href in hrefs or []:
            if not isinstance(href, str):
                continue
            abs_url = absolutize(profile_url, href.split("?")[0])
            if pattern and not pattern.search(urlparse(abs_url).path):
                continue
            if platform == "instagram" and "/p/" not in abs_url and "/reel/" not in abs_url and "/tv/" not in abs_url:
                continue
            if abs_url in seen:
                continue
            seen.add(abs_url)
            found.append(abs_url)
            if len(found) >= limit:
                return found
        await page.mouse.wheel(0, 1400)
        await page.wait_for_timeout(700)
    return found


async def parse_post_page(page: Page, *, platform: str, post_url: str) -> dict[str, Any]:
    """Extract caption, media URL, metrics, posted_at from an open post page."""
    platform = normalize_platform(platform)
    data = await page.evaluate(
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
            title: document.title || '',
          };
        }"""
    )

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

    # Aria-labels often carry "1,234 likes"
    aria_bits = await page.eval_on_selector_all(
        "[aria-label]",
        "els => els.map(e => e.getAttribute('aria-label')).filter(Boolean).slice(0, 80)",
    )
    for label in aria_bits or []:
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
        # Prefer larger-looking CDN urls
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
        m = pattern.search(path)
        if m:
            return f"{platform}:{m.group(1)}"[:100]
    slug = path.strip("/").replace("/", "-")[-60:] or "post"
    return f"{platform}:{slug}"[:100]
