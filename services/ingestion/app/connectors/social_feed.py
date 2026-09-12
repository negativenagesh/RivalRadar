"""Per-post social feed scout (Instagram, LinkedIn, X).

OSS-first (Instaloader / gallery-dl / linkedin_scraper), Playwright fallback.
TikTok is skipped by product request. Each platform runs in its own budgeted
task so one hang cannot stall the others.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import download_media_to_store, store_bytes
from app.connectors.oss.instagram import InstaloaderError, fetch_instagram_instaloader
from app.connectors.oss.linkedin import LinkedInScraperError, fetch_linkedin_company_posts
from app.connectors.oss.x_gallery import GalleryDlError, fetch_x_gallery_dl
from app.connectors.session_cookies import cookies_from_sessions, storage_state_from_sessions
from app.connectors.social_feed_parse import (
    collect_post_urls,
    normalize_platform,
    parse_post_page,
    settle_page,
)
from app.connectors.social_profile.browser import BrowserSession
from app.connectors.social_profile.targets import ProfileTarget
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)

_AGENT_ID = "ingestion.socialfeed"
_SERVICE = "ingestion"
_MAX_POSTS = 25
_PLATFORM_BUDGET_S = 180
_COLLECT_BUDGET_S = 35
_SKIP_PLATFORMS = {"tiktok"}


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
        self._targets = [
            t for t in targets if normalize_platform(t.platform or "") not in _SKIP_PLATFORMS
        ]
        skipped = [
            t for t in targets if normalize_platform(t.platform or "") in _SKIP_PLATFORMS
        ]
        self._skipped = skipped
        self._window = window
        self._headless = headless
        self._record = record
        self._event_bus = event_bus
        self._human_pause = human_pause
        self._object_store = object_store
        self._platform_sessions = platform_sessions or {}
        self._session: BrowserSession | None = None
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._accounts: list[RawAccount] = []
        self._posts: list[RawPost] = []
        self._screenshot_keys: list[str] = []
        self._loaded = False
        self._sources_used: list[str] = []
        self._video_path: Path | None = None

    @property
    def recorded_video_path(self) -> Path | None:
        if self._video_path is not None:
            return self._video_path
        return self._session.recorded_video_path if self._session else None

    @property
    def sources_used(self) -> list[str]:
        return list(self._sources_used) or ["browser"]

    @property
    def screenshot_keys(self) -> list[str]:
        return list(self._screenshot_keys)

    async def aclose(self) -> None:
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
        for t in self._skipped:
            await self._emit(
                "action",
                {"detail": f"skip_platform platform={normalize_platform(t.platform)} reason=disabled"},
            )
        platforms = sorted(
            {normalize_platform(t.platform) for t in self._targets if t.platform}
        )
        all_cookies = cookies_from_sessions(self._platform_sessions, platforms=set(platforms))
        all_state = storage_state_from_sessions(self._platform_sessions, platforms=set(platforms))
        if all_cookies or all_state:
            await self._emit(
                "action",
                {
                    "detail": (
                        f"connect_session cookies={len(all_cookies)} "
                        f"storage_state={'yes' if all_state else 'no'} "
                        f"platforms={platforms}"
                    )
                },
            )
        await self._emit(
            "action",
            {
                "detail": (
                    f"scouting_parallel platforms={platforms} budget_s={_PLATFORM_BUDGET_S} "
                    f"oss=instaloader,gallery-dl,linkedin_scraper"
                )
            },
        )

        results = await asyncio.gather(
            *(
                self._scout_target_isolated(target, record=(i == 0 and self._record))
                for i, target in enumerate(self._targets)
            ),
            return_exceptions=True,
        )
        for target, result in zip(self._targets, results, strict=True):
            if isinstance(result, Exception):
                platform = normalize_platform(target.platform or "web")
                await self._emit(
                    "error",
                    {"detail": f"scout_target failed {platform}: {result}"},
                )
                logger.exception("scout_target failed for %s", target.handle, exc_info=result)

        self._loaded = True
        if not self._sources_used:
            self._sources_used.append("browser")

    async def _scout_target_isolated(self, target: ProfileTarget, *, record: bool) -> None:
        platform = normalize_platform(target.platform or "web")
        try:
            await asyncio.wait_for(
                self._scout_with_oss_then_browser(target, record=record),
                timeout=_PLATFORM_BUDGET_S,
            )
        except TimeoutError:
            await self._emit(
                "error",
                {
                    "detail": (
                        f"platform_budget_exceeded {platform} "
                        f"after {_PLATFORM_BUDGET_S}s — continuing other platforms"
                    )
                },
            )

    async def _scout_with_oss_then_browser(self, target: ProfileTarget, *, record: bool) -> None:
        platform = normalize_platform(target.platform or "web")
        url = _profile_entry_url(target, platform)
        handle = _handle_for(target, url)

        # --- OSS first ---
        try:
            await self._emit(
                "action",
                {"detail": f"oss_try platform={platform} window={self._window.date_from}→{self._window.date_to}"},
            )
            account, posts = await self._oss_fetch(platform, handle=handle, url=url)
            async with self._lock:
                self._accounts.append(account)
                self._posts.extend(posts)
                source = {
                    "instagram": "instaloader",
                    "x": "gallery_dl",
                    "linkedin": "linkedin_scraper",
                }.get(platform, "oss")
                if source not in self._sources_used:
                    self._sources_used.append(source)
            await self._emit(
                "action",
                {"detail": f"found_posts count={len(posts)} platform={platform} source=oss"},
            )
            await self._emit(
                "action",
                {
                    "detail": (
                        f"ingested_posts count={len(posts)} platform={platform} "
                        f"window={self._window.date_from}→{self._window.date_to} source=oss"
                    )
                },
            )
            for p in posts[:8]:
                await self._emit(
                    "action",
                    {
                        "detail": "parsed_post",
                        "platform": platform,
                        "id": p["external_post_id"],
                        "likes": p["likes"],
                        "comments": p["comments"],
                        "views": p.get("views", 0),
                        "has_media": bool(p.get("media_keys") or p.get("media_urls")),
                    },
                )
            return
        except (InstaloaderError, GalleryDlError, LinkedInScraperError, RuntimeError) as exc:
            await self._emit(
                "action",
                {"detail": f"oss_fallback platform={platform} reason={exc}"},
            )
            logger.info("OSS fallback for %s: %s", platform, exc)

        # --- Playwright fallback ---
        cookies = cookies_from_sessions(self._platform_sessions, platforms={platform})
        storage_state = storage_state_from_sessions(self._platform_sessions, platforms={platform})
        async with BrowserSession(
            headless=self._headless,
            record=record,
            cookies=cookies,
            storage_state=storage_state,
        ) as session:
            if record:
                self._session = session
            await self._scout_target_browser(session, target)
            if record and session.recorded_video_path:
                self._video_path = session.recorded_video_path
        async with self._lock:
            if "browser" not in self._sources_used:
                self._sources_used.append("browser")

    async def _oss_fetch(
        self, platform: str, *, handle: str, url: str
    ) -> tuple[RawAccount, list[RawPost]]:
        if platform == "instagram":
            return await fetch_instagram_instaloader(
                run_id=self._run_id,
                handle=handle,
                url=url,
                window=self._window,
                platform_sessions=self._platform_sessions,
                object_store=self._object_store,
                max_posts=_MAX_POSTS,
            )
        if platform == "x":
            return await fetch_x_gallery_dl(
                run_id=self._run_id,
                handle=handle,
                url=url,
                window=self._window,
                platform_sessions=self._platform_sessions,
                object_store=self._object_store,
                max_posts=_MAX_POSTS,
            )
        if platform == "linkedin":
            cookies = cookies_from_sessions(self._platform_sessions, platforms={"linkedin"})
            storage_state = storage_state_from_sessions(
                self._platform_sessions, platforms={"linkedin"}
            )
            async with BrowserSession(
                headless=self._headless,
                record=False,
                cookies=cookies,
                storage_state=storage_state,
            ) as session:
                assert session.page is not None
                return await fetch_linkedin_company_posts(
                    page=session.page,
                    run_id=self._run_id,
                    handle=handle,
                    url=url,
                    window=self._window,
                    platform_sessions=self._platform_sessions,
                    object_store=self._object_store,
                    max_posts=_MAX_POSTS,
                )
        raise RuntimeError(f"no oss scraper for {platform}")

    async def _pause(self, *, short: bool = False) -> None:
        if not self._human_pause:
            return
        delay = random.uniform(0.25, 0.55) if short else random.uniform(0.8, 1.5)
        if not short:
            await self._emit("action", {"detail": f"human_pause {delay:.1f}s"})
        await asyncio.sleep(delay)

    async def _scout_target_browser(self, session: BrowserSession, target: ProfileTarget) -> None:
        assert session.page is not None
        page = session.page
        platform = normalize_platform(target.platform or "web")
        url = _profile_entry_url(target, platform)
        handle = _handle_for(target, url)

        await self._emit("nav", {"url": url, "platform": platform, "phase": "profile"})
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await settle_page(page)
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"profile nav failed {url}: {exc}"})
            async with self._lock:
                self._accounts.append(
                    RawAccount(handle=handle, display_name=handle, platform=platform)
                )
            return

        await self._pause()
        await self._emit("action", {"detail": f"reading_profile platform={platform}"})
        try:
            await settle_page(page, quiet_ms=300)
            title = await asyncio.wait_for(page.title(), timeout=8)
        except Exception:  # noqa: BLE001
            title = handle
        display = (title or handle).split("•")[0].split("|")[0].strip()[:200] or handle
        async with self._lock:
            self._accounts.append(
                RawAccount(handle=handle, display_name=display, platform=platform)
            )

        try:
            await self._emit("action", {"detail": f"screenshot platform={platform}"})
            await settle_page(page, quiet_ms=150)
            jpeg = await asyncio.wait_for(session.screenshot_jpeg_b64(), timeout=12)
            await self._emit(
                "screenshot",
                {
                    "jpeg_b64": jpeg,
                    "platform": platform,
                    "url": url,
                    "label": f"{handle} profile",
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("profile screenshot skipped", exc_info=True)
            await self._emit("action", {"detail": f"screenshot_skipped platform={platform}"})

        await self._emit("action", {"detail": f"collecting_posts platform={platform}"})
        try:
            post_urls = await asyncio.wait_for(
                collect_post_urls(
                    page,
                    platform=platform,
                    profile_url=url,
                    limit=_MAX_POSTS,
                    max_scrolls=4,
                ),
                timeout=_COLLECT_BUDGET_S,
            )
        except TimeoutError:
            await self._emit(
                "error",
                {"detail": f"collect_posts timed out {platform} — continuing"},
            )
            post_urls = []
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"collect_posts failed {platform}: {exc}"})
            post_urls = []

        await self._emit(
            "action",
            {"detail": f"found_posts count={len(post_urls)} platform={platform} source=browser"},
        )

        kept = 0
        for post_url in post_urls:
            if kept >= _MAX_POSTS:
                break
            try:
                ok = await self._ingest_post(
                    session,
                    handle=handle,
                    platform=platform,
                    post_url=post_url,
                )
            except Exception as exc:  # noqa: BLE001
                await self._emit("error", {"detail": f"ingest_post failed {post_url}: {exc}"})
                ok = False
            if ok:
                kept += 1

        await self._emit(
            "action",
            {
                "detail": (
                    f"ingested_posts count={kept} platform={platform} "
                    f"window={self._window.date_from}→{self._window.date_to} source=browser"
                ),
            },
        )

    async def _ingest_post(
        self,
        session: BrowserSession,
        *,
        handle: str,
        platform: str,
        post_url: str,
    ) -> bool:
        assert session.page is not None
        page = session.page
        await self._emit("nav", {"url": post_url, "platform": platform, "phase": "post"})
        try:
            await page.goto(post_url, wait_until="domcontentloaded", timeout=35000)
            await settle_page(page)
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"post nav failed {post_url}: {exc}"})
            return False

        await self._pause(short=True)
        try:
            parsed = await parse_post_page(page, platform=platform, post_url=post_url)
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"parse_post failed {post_url}: {exc}"})
            return False
        posted_at: datetime | None = parsed.get("posted_at")
        if posted_at is None:
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
                session,
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
        async with self._lock:
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

    async def _download_post_media(
        self,
        session: BrowserSession,
        *,
        post_id: str,
        media_url: str,
    ) -> str | None:
        assert session.page is not None
        assert self._object_store is not None
        page = session.page
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
        async with self._lock:
            self._sequence += 1
            seq = self._sequence
        await self._event_bus.publish(
            AgentEvent(
                run_id=self._run_id,
                agent_id=_AGENT_ID,
                service=_SERVICE,
                step_type=step_type,
                payload=payload,
                sequence=seq,
            )
        )


def _profile_entry_url(target: ProfileTarget, platform: str) -> str:
    url = (target.url or target.handle or "").strip()
    if not url.startswith("http"):
        url = f"https://{url}"
    if platform != "linkedin":
        return url
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if (
        "/company/" in path
        and not path.endswith(("/posts", "/recent-activity", "/all"))
        and "/posts" not in path
        and "/recent-activity" not in path
    ):
        path = f"{path}/posts"
        return parsed._replace(path=path).geturl()
    return url


def _handle_for(target: ProfileTarget, url: str) -> str:
    raw = (target.handle or "").strip()
    if not raw:
        path = urlparse(url).path.strip("/")
        raw = path.split("/")[0] if path else urlparse(url).netloc
    raw = re.sub(r"[^\w.@-]+", ".", raw)[:80]
    if not raw.startswith("@"):
        raw = f"@{raw}"
    return raw[:100]
