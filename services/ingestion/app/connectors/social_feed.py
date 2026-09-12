"""Per-post social feed scout (Instagram, LinkedIn, X, TikTok, Threads).

Visits each post in the date window, downloads real media (not screenshots),
and parses likes / comments / views / shares for Findings.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import download_media_to_store, store_bytes
from app.connectors.session_cookies import cookies_from_sessions
from app.connectors.social_feed_parse import (
    collect_post_urls,
    normalize_platform,
    parse_post_page,
)
from app.connectors.social_profile.browser import BrowserSession
from app.connectors.social_profile.targets import ProfileTarget
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)

_AGENT_ID = "ingestion.socialfeed"
_SERVICE = "ingestion"
_MAX_POSTS = 30


class SocialFeedConnector:
    def __init__(
        self,
        run_id: str,
        targets: list[ProfileTarget],
        *,
        window: DateWindow,
        headless: bool = True,
        record: bool = False,
        event_bus: AgentEventBus | None = None,
        human_pause: bool = True,
        object_store: ObjectStore | None = None,
        platform_sessions: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._run_id = run_id
        self._targets = targets
        self._window = window
        self._headless = headless
        self._record = record
        self._event_bus = event_bus
        self._human_pause = human_pause
        self._object_store = object_store
        self._platform_sessions = platform_sessions or {}
        self._session: BrowserSession | None = None
        self._sequence = 0
        self._accounts: list[RawAccount] = []
        self._posts: list[RawPost] = []
        self._screenshot_keys: list[str] = []
        self._loaded = False
        self._sources_used: list[str] = []

    @property
    def recorded_video_path(self) -> Path | None:
        return self._session.recorded_video_path if self._session else None

    @property
    def sources_used(self) -> list[str]:
        return list(self._sources_used) or ["browser"]

    @property
    def screenshot_keys(self) -> list[str]:
        return list(self._screenshot_keys)

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

    async def fetch_accounts(self) -> list[RawAccount]:
        await self._ensure_loaded()
        return list(self._accounts)

    async def fetch_posts(self) -> list[RawPost]:
        await self._ensure_loaded()
        return list(self._posts)

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        platforms = {normalize_platform(t.platform) for t in self._targets if t.platform}
        cookies = cookies_from_sessions(self._platform_sessions, platforms=platforms)
        if cookies:
            await self._emit(
                "action",
                {"detail": f"connect_session cookies={len(cookies)} platforms={sorted(platforms)}"},
            )
        self._session = await BrowserSession(
            headless=self._headless,
            record=self._record,
            cookies=cookies,
        ).__aenter__()
        assert self._session.page is not None
        for target in self._targets:
            await self._scout_target(target)
        self._loaded = True
        self._sources_used.append("browser")

    async def _pause(self) -> None:
        if not self._human_pause:
            return
        delay = random.uniform(1.2, 2.4)
        await self._emit("action", {"detail": f"human_pause {delay:.1f}s"})
        await asyncio.sleep(delay)

    async def _scout_target(self, target: ProfileTarget) -> None:
        assert self._session is not None and self._session.page is not None
        page = self._session.page
        platform = normalize_platform(target.platform or "web")
        url = target.url or target.handle
        if not url.startswith("http"):
            url = f"https://{url}"

        handle = _handle_for(target, url)
        await self._emit("nav", {"url": url, "platform": platform, "phase": "profile"})
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"profile nav failed {url}: {exc}"})
            self._accounts.append(
                RawAccount(handle=handle, display_name=handle, platform=platform)
            )
            return

        await self._pause()
        title = await page.title()
        display = (title or handle).split("•")[0].split("|")[0].strip()[:200] or handle
        self._accounts.append(
            RawAccount(handle=handle, display_name=display, platform=platform)
        )

        # Operator theater only — never used as Findings media
        try:
            jpeg = await self._session.screenshot_jpeg_b64()
            await self._emit(
                "screenshot",
                {"jpeg_b64": jpeg, "platform": platform, "url": url, "label": f"{handle} profile"},
            )
        except Exception:  # noqa: BLE001
            logger.debug("profile screenshot skipped", exc_info=True)

        post_urls = await collect_post_urls(page, platform=platform, profile_url=url, limit=_MAX_POSTS)
        await self._emit(
            "action",
            {"detail": f"found_posts count={len(post_urls)} platform={platform}"},
        )

        kept = 0
        for post_url in post_urls:
            if kept >= _MAX_POSTS:
                break
            ok = await self._ingest_post(
                handle=handle,
                platform=platform,
                post_url=post_url,
            )
            if ok:
                kept += 1

        await self._emit(
            "action",
            {
                "detail": f"ingested_posts count={kept} platform={platform} "
                f"window={self._window.date_from}→{self._window.date_to}",
            },
        )

    async def _ingest_post(self, *, handle: str, platform: str, post_url: str) -> bool:
        assert self._session is not None and self._session.page is not None
        page = self._session.page
        await self._emit("nav", {"url": post_url, "platform": platform, "phase": "post"})
        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"post nav failed {post_url}: {exc}"})
            return False

        await self._pause()
        parsed = await parse_post_page(page, platform=platform, post_url=post_url)
        posted_at: datetime | None = parsed.get("posted_at")
        if posted_at is None:
            # Keep recent undated posts only if still scanning early grid
            posted_at = datetime.now(UTC)
            uncertain = True
        else:
            uncertain = False
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=UTC)
            if not self._window.contains(posted_at):
                return False

        media_url = parsed.get("media_url")
        media_keys: list[str] = []
        media_urls: list[str] = [media_url] if isinstance(media_url, str) and media_url else []
        image_url: str | None = media_urls[0] if media_urls else None

        if self._object_store and media_urls:
            key = await self._download_post_media(
                post_id=str(parsed["external_post_id"]),
                media_url=media_urls[0],
            )
            if key:
                media_keys = [key]
                image_url = f"/ingestion/media/{key}"

        themes = [
            platform,
            "source:browser",
            f"link:{post_url[:180]}",
            f"date_from:{self._window.date_from.isoformat()}",
            f"date_to:{self._window.date_to.isoformat()}",
        ]
        if uncertain:
            themes.append("posted_at_uncertain")

        fmt = "reel" if "/reel/" in post_url or platform == "tiktok" else "founder_post"
        post: RawPost = {
            "account_handle": handle,
            "external_post_id": str(parsed["external_post_id"])[:100],
            "format": fmt,
            "theme_tags": themes,
            "caption": str(parsed.get("caption") or "")[:2000],
            "image_url": image_url,
            "likes": int(parsed.get("likes") or 0),
            "comments": int(parsed.get("comments") or 0),
            "shares": int(parsed.get("shares") or 0),
            "views": int(parsed.get("views") or 0),
            "posted_at": posted_at.isoformat().replace("+00:00", "Z"),
            "media_urls": media_urls,
            "media_keys": media_keys,
        }
        self._posts.append(post)
        await self._emit(
            "action",
            {
                "detail": "parsed_post",
                "platform": platform,
                "id": post["external_post_id"],
                "likes": post["likes"],
                "comments": post["comments"],
                "views": post.get("views", 0),
                "has_media": bool(media_keys or media_urls),
            },
        )
        return True

    async def _download_post_media(self, *, post_id: str, media_url: str) -> str | None:
        assert self._session is not None and self._session.page is not None
        assert self._object_store is not None
        page = self._session.page
        # Prefer authenticated browser fetch (Instagram CDN often needs session)
        try:
            resp = await page.request.get(media_url, timeout=30000)
            if resp.ok:
                body = await resp.body()
                ctype = resp.headers.get("content-type", "image/jpeg")
                key = await store_bytes(
                    self._object_store,
                    run_id=self._run_id,
                    post_id=post_id,
                    data=body,
                    content_type=ctype,
                )
                if key:
                    return key
        except Exception as exc:  # noqa: BLE001
            logger.info("page.request media failed %s: %s", post_id, exc)

        return await download_media_to_store(
            self._object_store,
            run_id=self._run_id,
            post_id=post_id,
            url=media_url,
        )

    async def _emit(self, step_type: StepType, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._sequence += 1
        await self._event_bus.publish(
            AgentEvent(
                run_id=self._run_id,
                agent_id=_AGENT_ID,
                service=_SERVICE,
                step_type=step_type,
                payload=payload,
                sequence=self._sequence,
            )
        )


def _handle_for(target: ProfileTarget, url: str) -> str:
    import re
    from urllib.parse import urlparse

    raw = (target.handle or "").strip()
    if not raw:
        path = urlparse(url).path.strip("/")
        raw = path.split("/")[0] if path else urlparse(url).netloc
    raw = re.sub(r"[^\w.@-]+", ".", raw)[:80]
    if not raw.startswith("@"):
        raw = f"@{raw}"
    return raw[:100]
