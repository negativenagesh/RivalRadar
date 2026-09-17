"""Per-post social feed scout (Instagram, LinkedIn, X).

OSS-first (Instaloader / gallery-dl / linkedin_scraper), Playwright fallback.
TikTok is skipped by product request. Targets run sequentially with a per-target
budget so cookie/browser tools do not contend with each other.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import random
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import download_media_to_store, download_via_page, store_bytes
from app.connectors.oss.instagram import InstaloaderError, fetch_instagram_instaloader
from app.connectors.oss.linkedin import LinkedInScraperError, fetch_linkedin_company_posts
from app.connectors.oss.x_gallery import GalleryDlError, fetch_x_gallery_dl
from app.connectors.session_cookies import cookies_from_sessions, storage_state_from_sessions
from app.connectors.social_feed_parse import (
    collect_post_urls,
    normalize_platform,
    parse_post_page,
    posted_at_from_linkedin_activity,
    posted_at_from_url,
    settle_page,
)
from app.connectors.social_profile.browser import (
    BrowserSession,
    await_or_abandon,
    browser_engine,
)
from app.connectors.social_profile.targets import ProfileTarget
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)

_AGENT_ID = "ingestion.socialfeed"
_SERVICE = "ingestion"
_MAX_POSTS = 40
_PLATFORM_BUDGET_S = 120
_OSS_BUDGET_S = 50
# linkedin_scraper often ignores cancel on Obscura/CDP; keep Chromium OSS short
# so browser fallback still fits inside the platform budget.
_LINKEDIN_OSS_BUDGET_S = 25
_GOTO_MS = 20_000
_HEARTBEAT_S = 3
_COLLECT_BUDGET_S = 40
_POST_BUDGET_S = 35
# Reverse-chrono feeds: stop after this many posts older than date_from.
_PAST_WINDOW_STOP = 3
_SKIP_PLATFORMS = {"tiktok"}
# On Obscura, HTTP OSS (Instaloader / gallery-dl) before LinkedIn browser work.
_OBSCURA_SCOUT_PRIORITY = {"instagram": 0, "x": 1, "twitter": 1, "linkedin": 2}


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
        skipped = [t for t in targets if normalize_platform(t.platform or "") in _SKIP_PLATFORMS]
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
        self._media_counts: dict[str, dict[str, int]] = {}
        self._screenshot_keys: list[str] = []
        self._loaded = False
        self._sources_used: list[str] = []
        self._video_path: Path | None = None
        self._checkpoint: Callable[[], Awaitable[None]] | None = None

    def set_checkpoint(self, fn: Callable[[], Awaitable[None]] | None) -> None:
        self._checkpoint = fn

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

    _VIDEO_EXTS = (".mp4", ".webm", ".mov", ".mkv")

    def _count_media(self, platform: str, post: RawPost) -> None:
        """Track stored-media shape per platform for the ingest summary + logs."""
        bucket = self._media_counts.setdefault(platform, {"img": 0, "vid": 0, "none": 0})
        key = (post.get("media_keys") or [""])[0].lower()
        if not key:
            bucket["none"] += 1
        elif key.endswith(self._VIDEO_EXTS):
            bucket["vid"] += 1
        else:
            bucket["img"] += 1

    def _media_summary(self, platform: str) -> str:
        bucket = self._media_counts.get(platform, {"img": 0, "vid": 0, "none": 0})
        return f"media_imgs={bucket['img']} media_vids={bucket['vid']} media_none={bucket['none']}"

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
                {
                    "detail": f"skip_platform platform={normalize_platform(t.platform)} reason=disabled"
                },
            )
        ordered = _order_targets_for_engine(self._targets)
        platforms = sorted({normalize_platform(t.platform) for t in ordered if t.platform})
        all_cookies = cookies_from_sessions(self._platform_sessions, platforms=set(platforms))
        all_state = storage_state_from_sessions(self._platform_sessions, platforms=set(platforms))
        if all_cookies or all_state:
            await self._emit(
                "action",
                {
                    "detail": (
                        f"connect_session source=extension_vault "
                        f"cookies={len(all_cookies)} "
                        f"storage_state={'yes' if all_state else 'no'} "
                        f"platforms={platforms}"
                    )
                },
            )
        engine = browser_engine()
        await self._emit(
            "action",
            {
                "detail": (
                    f"scouting_sequential platforms={platforms} "
                    f"targets={len(ordered)} budget_s={_PLATFORM_BUDGET_S} "
                    f"window={self._window.date_from}→{self._window.date_to} "
                    f"engine={engine} oss=instaloader,gallery-dl,linkedin_scraper"
                )
            },
        )

        # One target at a time — parallel Chromium/Instaloader/gallery-dl fights
        # Connect cookies and produces interleaved event-log noise.
        for i, target in enumerate(ordered):
            platform = normalize_platform(target.platform or "web")
            await self._emit(
                "action",
                {
                    "detail": (
                        f"scout_next platform={platform} "
                        f"target={i + 1}/{len(ordered)} handle={target.handle}"
                    )
                },
            )
            try:
                await self._scout_target_isolated(target, record=(i == 0 and self._record))
            except Exception as exc:  # noqa: BLE001
                await self._emit(
                    "error",
                    {"detail": f"scout_target failed {platform}: {exc}"},
                )
                logger.exception("scout_target failed for %s", target.handle)
            await self._flush_checkpoint()

        self._loaded = True
        if not self._sources_used:
            self._sources_used.append("browser")

    async def _scout_target_isolated(self, target: ProfileTarget, *, record: bool) -> None:
        platform = normalize_platform(target.platform or "web")
        try:
            await await_or_abandon(
                self._scout_with_oss_then_browser(target, record=record),
                _PLATFORM_BUDGET_S,
            )
        except TimeoutError:
            await self._emit(
                "error",
                {
                    "detail": (
                        f"platform_budget_exceeded {platform} "
                        f"after {_PLATFORM_BUDGET_S}s — continuing next target"
                    )
                },
            )

    async def _scout_with_oss_then_browser(self, target: ProfileTarget, *, record: bool) -> None:
        platform = normalize_platform(target.platform or "web")
        if platform == "linkedin":
            await self._scout_linkedin(target, record=record)
            return

        url = _profile_entry_url(target, platform)
        handle = _handle_for(target, url)

        # --- OSS first (bounded) ---
        try:
            await self._emit(
                "action",
                {
                    "detail": f"oss_try platform={platform} window={self._window.date_from}→{self._window.date_to}"
                },
            )
            account, posts = await self._oss_fetch_bounded(platform, handle=handle, url=url)
            if not posts:
                raise RuntimeError("oss returned 0 posts in date window")
            await self._commit_oss_posts(account, posts, platform=platform)
            return
        except (
            InstaloaderError,
            GalleryDlError,
            LinkedInScraperError,
            RuntimeError,
            TimeoutError,
        ) as exc:
            await self._emit(
                "action",
                {"detail": f"oss_fallback platform={platform} reason={exc}"},
            )
            logger.info("OSS fallback for %s: %s", platform, exc)

        await self._browser_fallback(target, record=record)

    async def _commit_oss_posts(
        self, account: RawAccount, posts: list[RawPost], *, platform: str
    ) -> None:
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
        for p in posts:
            self._count_media(platform, p)
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
            await self._emit_stored_media_frame(p, platform=platform)
        summary = self._media_summary(platform)
        logger.info("scout media summary platform=%s source=oss %s", platform, summary)
        await self._emit(
            "action",
            {
                "detail": (
                    f"ingested_posts count={len(posts)} platform={platform} "
                    f"window={self._window.date_from}→{self._window.date_to} source=oss {summary}"
                )
            },
        )
        await self._emit(
            "action",
            {"detail": f"media_summary platform={platform} source=oss {summary}"},
        )
        await self._flush_checkpoint()

    async def _browser_fallback(self, target: ProfileTarget, *, record: bool) -> None:
        platform = normalize_platform(target.platform or "web")
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

    async def _oss_fetch_bounded(
        self, platform: str, *, handle: str, url: str
    ) -> tuple[RawAccount, list[RawPost]]:
        stop = asyncio.Event()
        hb = asyncio.create_task(self._oss_heartbeat(platform=platform, stop=stop))
        try:
            return await await_or_abandon(
                self._oss_fetch(platform, handle=handle, url=url),
                _OSS_BUDGET_S,
            )
        except TimeoutError:
            raise TimeoutError(f"oss timed out after {_OSS_BUDGET_S}s") from None
        finally:
            stop.set()
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb

    async def _oss_heartbeat(self, *, platform: str, stop: asyncio.Event) -> None:
        elapsed = 0
        while not stop.is_set():
            await self._emit(
                "action",
                {"detail": f"oss_working platform={platform} elapsed={elapsed}s"},
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=_HEARTBEAT_S)
                return
            except TimeoutError:
                elapsed += _HEARTBEAT_S

    async def _scout_linkedin(self, target: ProfileTarget, *, record: bool) -> None:
        """LinkedIn: OSS scraper on Chromium; Obscura uses browser + extension vault.

        ``linkedin_scraper`` can block the asyncio event loop on Obscura CDP so
        platform budgets never fire. Extension-vault cookies + browser collect is
        the supported Obscura path.
        """
        platform = "linkedin"
        cookies = cookies_from_sessions(self._platform_sessions, platforms={platform})
        if browser_engine() == "obscura":
            await self._emit(
                "action",
                {
                    "detail": (
                        "oss_fallback platform=linkedin "
                        "reason=obscura_browser_with_extension_vault "
                        f"cookies={len(cookies)}"
                    )
                },
            )
            if not cookies:
                await self._emit(
                    "error",
                    {
                        "detail": (
                            "linkedin needs Connect extension cookies on Obscura "
                            "(pair via RivalRadar Connect)"
                        )
                    },
                )
                # Login wall hangs forever without cookies — do not open Obscura.
                return
            await self._browser_fallback(target, record=record)
            return

        url = _profile_entry_url(target, platform)
        handle = _handle_for(target, url)
        storage_state = storage_state_from_sessions(self._platform_sessions, platforms={platform})
        await self._emit(
            "action",
            {
                "detail": (
                    f"oss_try platform={platform} "
                    f"window={self._window.date_from}→{self._window.date_to}"
                )
            },
        )
        stop = asyncio.Event()
        hb = asyncio.create_task(self._oss_heartbeat(platform=platform, stop=stop))
        oss_ok = False
        try:
            async with BrowserSession(
                headless=self._headless,
                record=record,
                cookies=cookies,
                storage_state=storage_state,
            ) as session:
                if record:
                    self._session = session
                assert session.page is not None
                await self._emit("nav", {"url": url, "platform": platform, "phase": "profile"})
                try:
                    await await_or_abandon(
                        session.page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_MS),
                        min(_LINKEDIN_OSS_BUDGET_S, _GOTO_MS / 1000 + 5),
                    )
                    await settle_page(session.page, quiet_ms=80)
                except TimeoutError:
                    await self._emit(
                        "error",
                        {"detail": f"linkedin oss nav timed out after {_GOTO_MS}ms"},
                    )
                except Exception as exc:  # noqa: BLE001
                    await self._emit("error", {"detail": f"linkedin oss nav: {exc}"})
                try:
                    account, posts = await await_or_abandon(
                        fetch_linkedin_company_posts(
                            page=session.page,
                            run_id=self._run_id,
                            handle=handle,
                            url=url,
                            window=self._window,
                            platform_sessions=self._platform_sessions,
                            object_store=self._object_store,
                            max_posts=_MAX_POSTS,
                        ),
                        _LINKEDIN_OSS_BUDGET_S,
                    )
                    if posts:
                        await self._commit_oss_posts(account, posts, platform=platform)
                        await self._hydrate_missing_media(
                            session,
                            posts,
                            platform=platform,
                            handle=handle,
                        )
                        oss_ok = True
                    else:
                        await self._emit(
                            "action",
                            {"detail": "oss_fallback platform=linkedin reason=0 posts in window"},
                        )
                except TimeoutError:
                    await self._emit(
                        "action",
                        {
                            "detail": (
                                f"oss_fallback platform=linkedin "
                                f"reason=timed out after {_LINKEDIN_OSS_BUDGET_S}s"
                            )
                        },
                    )
                except LinkedInScraperError as exc:
                    await self._emit(
                        "action",
                        {"detail": f"oss_fallback platform=linkedin reason={exc}"},
                    )
                stop.set()
                hb.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await hb
                if oss_ok:
                    if record and session.recorded_video_path:
                        self._video_path = session.recorded_video_path
                    return
                await self._scout_target_browser(session, target)
                if record and session.recorded_video_path:
                    self._video_path = session.recorded_video_path
        except RuntimeError as exc:
            await self._emit("error", {"detail": f"linkedin browser session: {exc}"})
        finally:
            if not stop.is_set():
                stop.set()
                hb.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await hb
        if not oss_ok:
            await self._browser_fallback(target, record=record)
            return
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
            await await_or_abandon(
                page.goto(url, wait_until="domcontentloaded", timeout=_GOTO_MS),
                min(_PLATFORM_BUDGET_S, _GOTO_MS / 1000 + 5),
            )
            await settle_page(page)
        except TimeoutError:
            await self._emit(
                "error",
                {"detail": f"profile nav timed out after {_GOTO_MS}ms {url}"},
            )
            async with self._lock:
                self._accounts.append(
                    RawAccount(handle=handle, display_name=handle, platform=platform)
                )
            return
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

        await self._emit("action", {"detail": f"collecting_posts platform={platform}"})
        post_urls = await self._collect_post_urls_bounded(page, platform=platform, profile_url=url)

        await self._emit(
            "action",
            {"detail": f"found_posts count={len(post_urls)} platform={platform} source=browser"},
        )

        # Obscura + LinkedIn: listing URNs already encode timestamps. Skip per-post
        # navigations that OOM the 512MB Render dyno and leave runs wedged.
        if platform == "linkedin" and browser_engine() == "obscura":
            kept, skipped_outside = await self._ingest_linkedin_listing_only(
                handle=handle, post_urls=post_urls
            )
        else:
            kept = 0
            skipped_outside = 0
            consecutive_older = 0
            for post_url in post_urls:
                if kept >= _MAX_POSTS:
                    break
                try:
                    outcome = await self._ingest_post_bounded(
                        session,
                        handle=handle,
                        platform=platform,
                        post_url=post_url,
                    )
                except Exception as exc:  # noqa: BLE001
                    await self._emit("error", {"detail": f"ingest_post failed {post_url}: {exc}"})
                    outcome = "failed"
                if outcome == "kept":
                    kept += 1
                    consecutive_older = 0
                elif outcome == "older":
                    skipped_outside += 1
                    consecutive_older += 1
                    if consecutive_older >= _PAST_WINDOW_STOP:
                        await self._emit(
                            "action",
                            {
                                "detail": (
                                    f"past_window_stop platform={platform} "
                                    f"after={consecutive_older} older than {self._window.date_from}"
                                )
                            },
                        )
                        break
                elif outcome == "outside":
                    skipped_outside += 1
                    consecutive_older = 0
                else:
                    consecutive_older = 0

        summary = self._media_summary(platform)
        await self._emit(
            "action",
            {
                "detail": (
                    f"ingested_posts count={kept} platform={platform} "
                    f"window={self._window.date_from}→{self._window.date_to} "
                    f"skipped_outside={skipped_outside} source=browser {summary}"
                ),
            },
        )
        logger.info("scout media summary platform=%s source=browser %s", platform, summary)
        await self._emit(
            "action",
            {"detail": f"media_summary platform={platform} source=browser {summary}"},
        )

    async def _ingest_linkedin_listing_only(
        self, *, handle: str, post_urls: list[str]
    ) -> tuple[int, int]:
        """Persist LinkedIn posts from listing URLs only (no per-post page loads)."""
        await self._emit(
            "action",
            {
                "detail": (
                    f"linkedin_listing_only reason=obscura_memory candidates={len(post_urls)}"
                )
            },
        )
        kept = 0
        skipped_outside = 0
        consecutive_older = 0
        for post_url in post_urls:
            if kept >= _MAX_POSTS:
                break
            posted = posted_at_from_linkedin_activity(post_url) or posted_at_from_url(
                "linkedin", post_url
            )
            if posted is None:
                continue
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=UTC)
            if not self._window.contains(posted):
                outcome = self._skip_outside_outcome(posted)
                skipped_outside += 1
                if outcome == "older":
                    consecutive_older += 1
                    if consecutive_older >= _PAST_WINDOW_STOP:
                        break
                else:
                    consecutive_older = 0
                continue
            consecutive_older = 0
            external = re.sub(r"[^\w.:-]+", "-", f"linkedin:{post_url}")[:100]
            post = RawPost(
                account_handle=handle if handle.startswith("@") else f"@{handle.lstrip('@')}",
                external_post_id=external,
                format="founder_post",
                theme_tags=[
                    "linkedin",
                    "source:browser",
                    "source:linkedin_listing",
                    f"link:{post_url[:180]}",
                    f"date_from:{self._window.date_from.isoformat()}",
                    f"date_to:{self._window.date_to.isoformat()}",
                ],
                caption=f"LinkedIn {handle.lstrip('@')}",
                image_url=None,
                likes=0,
                comments=0,
                shares=0,
                views=0,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
                media_urls=[],
                media_keys=[],
            )
            async with self._lock:
                self._posts.append(post)
            kept += 1
            await self._emit(
                "action",
                {
                    "detail": "parsed_post",
                    "platform": "linkedin",
                    "id": external,
                    "likes": 0,
                    "comments": 0,
                    "views": 0,
                    "has_media": False,
                },
            )
        await self._flush_checkpoint()
        return kept, skipped_outside

    async def _collect_post_urls_bounded(
        self,
        page: Any,
        *,
        platform: str,
        profile_url: str,
    ) -> list[str]:
        stop = asyncio.Event()
        hb = asyncio.create_task(
            self._phase_heartbeat(label=f"collecting_posts platform={platform}", stop=stop)
        )
        scrolls = 4 if platform == "linkedin" and browser_engine() == "obscura" else 8
        budget = (
            min(_COLLECT_BUDGET_S, 35)
            if platform == "linkedin" and browser_engine() == "obscura"
            else _COLLECT_BUDGET_S
        )
        try:
            return await await_or_abandon(
                collect_post_urls(
                    page,
                    platform=platform,
                    profile_url=profile_url,
                    limit=_MAX_POSTS,
                    max_scrolls=scrolls,
                ),
                budget,
            )
        except TimeoutError:
            await self._emit(
                "error",
                {"detail": f"collect_posts timed out {platform} — continuing"},
            )
            return []
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"collect_posts failed {platform}: {exc}"})
            return []
        finally:
            stop.set()
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb

    async def _phase_heartbeat(self, *, label: str, stop: asyncio.Event) -> None:
        elapsed = 0
        while not stop.is_set():
            await self._emit("action", {"detail": f"{label} elapsed={elapsed}s"})
            try:
                await asyncio.wait_for(stop.wait(), timeout=_HEARTBEAT_S)
                return
            except TimeoutError:
                elapsed += _HEARTBEAT_S

    def _skip_outside_outcome(self, posted_at: datetime) -> str:
        """Classify outside-window posts for reverse-chrono early stop."""
        day = posted_at.astimezone(UTC).date() if posted_at.tzinfo else posted_at.date()
        if day < self._window.date_from:
            return "older"
        return "outside"

    async def _ingest_post_bounded(
        self,
        session: BrowserSession,
        *,
        handle: str,
        platform: str,
        post_url: str,
    ) -> str:
        try:
            return await await_or_abandon(
                self._ingest_post(session, handle=handle, platform=platform, post_url=post_url),
                _POST_BUDGET_S,
            )
        except TimeoutError:
            await self._emit(
                "error",
                {"detail": (f"ingest_post timed out after {_POST_BUDGET_S}s {post_url[:120]}")},
            )
            return "failed"

    async def _ingest_post(
        self,
        session: BrowserSession,
        *,
        handle: str,
        platform: str,
        post_url: str,
    ) -> str:
        """Return kept | older | outside | failed (no_date / nav / parse errors)."""
        assert session.page is not None
        page = session.page
        await self._emit("nav", {"url": post_url, "platform": platform, "phase": "post"})
        try:
            await await_or_abandon(
                page.goto(post_url, wait_until="domcontentloaded", timeout=_GOTO_MS),
                min(_POST_BUDGET_S, _GOTO_MS / 1000 + 2),
            )
            await settle_page(page)
        except TimeoutError:
            await self._emit(
                "error",
                {"detail": f"post nav timed out {post_url[:120]}"},
            )
            return "failed"
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"post nav failed {post_url}: {exc}"})
            return "failed"

        url_date = posted_at_from_url(platform, post_url)
        if url_date is not None:
            if url_date.tzinfo is None:
                url_date = url_date.replace(tzinfo=UTC)
            if not self._window.contains(url_date):
                day = url_date.astimezone(UTC).date()
                await self._emit(
                    "action",
                    {
                        "detail": (
                            f"skipped_post reason=outside_window day={day.isoformat()} "
                            f"{post_url[:120]}"
                        )
                    },
                )
                return self._skip_outside_outcome(url_date)
        await self._pause(short=True)
        try:
            parsed = await parse_post_page(
                page,
                platform=platform,
                post_url=post_url,
                skip_time_wait=url_date is not None,
            )
        except Exception as exc:  # noqa: BLE001
            await self._emit("error", {"detail": f"parse_post failed {post_url}: {exc}"})
            return "failed"
        posted_at: datetime | None = parsed.get("posted_at") or url_date
        if posted_at is None:
            await self._emit(
                "action",
                {"detail": f"skipped_post reason=no_date {post_url[:120]}"},
            )
            return "failed"
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=UTC)
        if not self._window.contains(posted_at):
            day = posted_at.astimezone(UTC).date()
            await self._emit(
                "action",
                {
                    "detail": (
                        f"skipped_post reason=outside_window day={day.isoformat()} {post_url[:120]}"
                    )
                },
            )
            return self._skip_outside_outcome(posted_at)

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

        likes = int(parsed.get("likes") or 0)
        comments = int(parsed.get("comments") or 0)
        shares = int(parsed.get("shares") or 0)
        views = int(parsed.get("views") or 0)
        themes = [
            platform,
            "source:browser",
            f"link:{post_url[:180]}",
            f"date_from:{self._window.date_from.isoformat()}",
            f"date_to:{self._window.date_to.isoformat()}",
        ]
        # Theme metric tags keep Findings correct even if column upsert was stale.
        if likes:
            themes.append(f"likes:{likes}")
        if comments:
            themes.append(f"comments:{comments}")
        if shares:
            themes.append(f"shares:{shares}")
        if views:
            themes.append(f"views:{views}")

        fmt = "reel" if "/reel/" in post_url or platform == "tiktok" else "founder_post"
        post: RawPost = {
            "account_handle": handle,
            "external_post_id": str(parsed["external_post_id"])[:100],
            "format": fmt,
            "theme_tags": themes,
            "caption": str(parsed.get("caption") or "")[:2000],
            "image_url": image_url,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "views": views,
            "posted_at": posted_at.isoformat().replace("+00:00", "Z"),
            "media_urls": media_urls,
            "media_keys": media_keys,
            "media_kind": str(parsed.get("media_kind") or "image"),
        }
        async with self._lock:
            self._posts.append(post)
        await self._emit(
            "action",
            {
                "detail": (
                    f"parsed_post id={post['external_post_id']} "
                    f"likes={likes} comments={comments} views={views} "
                    f"media={parsed.get('media_kind') or 'image'}"
                ),
                "platform": platform,
                "id": post["external_post_id"],
                "likes": likes,
                "comments": comments,
                "views": views,
                "has_media": bool(media_keys or media_urls),
            },
        )
        await self._emit_post_screenshot(
            session, platform=platform, url=post_url, handle=handle, post=post
        )
        # Count after screenshot so media_fallback JPEG is not media_none.
        self._count_media(platform, post)
        if post.get("media_keys"):
            await self._emit_stored_media_frame(post, platform=platform)
        return "kept"

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
        key = await download_via_page(
            self._object_store,
            page=page,
            run_id=self._run_id,
            post_id=post_id,
            url=media_url,
        )
        if key:
            logger.info("media stored post=%s key=%s via=page", post_id, key)
            return key
        key = await download_media_to_store(
            self._object_store,
            run_id=self._run_id,
            post_id=post_id,
            url=media_url,
        )
        if key:
            logger.info("media stored post=%s key=%s via=http", post_id, key)
        else:
            logger.info("media not stored post=%s src=%.100s", post_id, media_url)
        return key

    async def _flush_checkpoint(self) -> None:
        if self._checkpoint is None:
            return
        try:
            await self._checkpoint()
        except Exception:  # noqa: BLE001
            logger.exception("checkpoint persist failed")

    async def _emit_post_screenshot(
        self,
        session: BrowserSession,
        *,
        platform: str,
        url: str,
        handle: str,
        post: RawPost | None = None,
    ) -> None:
        try:
            # Live Operator theater — not the Findings media file (unless fallback).
            await self._emit(
                "action",
                {"detail": f"live_frame platform={platform} kind=post"},
            )
            if session.page is not None:
                await settle_page(session.page, quiet_ms=80)
            jpeg = await asyncio.wait_for(session.screenshot_jpeg_b64(), timeout=12)
            await self._emit(
                "screenshot",
                {
                    "jpeg_b64": jpeg,
                    "mime": "jpeg",
                    "platform": platform,
                    "url": url,
                    "handle": handle,
                    "label": f"{handle} live frame",
                    "theater": True,
                },
            )
            if post is not None and self._object_store is not None and not post.get("media_keys"):
                key = await store_bytes(
                    self._object_store,
                    run_id=self._run_id,
                    post_id=str(post["external_post_id"]),
                    data=base64.b64decode(jpeg),
                    content_type="image/jpeg",
                )
                if key:
                    post["media_keys"] = [key]
                    post["image_url"] = f"/ingestion/media/{key}"
                    logger.info(
                        "media_fallback=screenshot post=%s key=%s platform=%s",
                        post["external_post_id"],
                        key,
                        platform,
                    )
                    await self._emit(
                        "action",
                        {
                            "detail": (
                                f"media_fallback=screenshot platform={platform} "
                                f"post={post['external_post_id']}"
                            )
                        },
                    )
        except Exception:  # noqa: BLE001
            logger.debug("post screenshot skipped", exc_info=True)

    async def _hydrate_missing_media(
        self,
        session: BrowserSession,
        posts: list[RawPost],
        *,
        platform: str,
        handle: str,
    ) -> None:
        """Visit in-window posts that OSS stored without downloaded media."""
        if session.page is None:
            return
        page = session.page
        filled = 0
        for post in posts:
            if filled >= 15:
                break
            if post.get("media_keys"):
                continue
            link = _post_permalink(post, platform)
            if not link:
                continue
            await self._emit("nav", {"url": link, "platform": platform, "phase": "post"})
            try:
                await page.goto(link, wait_until="domcontentloaded", timeout=_GOTO_MS)
                await settle_page(page, quiet_ms=120)
            except Exception as exc:  # noqa: BLE001
                await self._emit("error", {"detail": f"hydrate nav failed {link}: {exc}"})
                continue
            media_url: str | None = None
            try:
                parsed = await parse_post_page(
                    page, platform=platform, post_url=link, skip_time_wait=True
                )
                raw = parsed.get("media_url")
                if isinstance(raw, str) and raw.startswith("http"):
                    media_url = raw
            except Exception:  # noqa: BLE001
                logger.debug("hydrate parse failed", exc_info=True)
            if media_url and self._object_store is not None:
                key = await self._download_post_media(
                    session,
                    post_id=str(post["external_post_id"]),
                    media_url=media_url,
                )
                if key:
                    post["media_keys"] = [key]
                    post["image_url"] = f"/ingestion/media/{key}"
                    urls = [u for u in (post.get("media_urls") or []) if u]
                    if media_url not in urls:
                        post["media_urls"] = [media_url, *urls]
                    await self._emit_stored_media_frame(post, platform=platform)
                    filled += 1
                    continue
            await self._emit_post_screenshot(
                session, platform=platform, url=link, handle=handle, post=post
            )
            filled += 1
        if filled:
            await self._flush_checkpoint()

    async def _emit_stored_media_frame(self, post: RawPost, *, platform: str) -> None:
        if self._object_store is None:
            return
        keys = list(post.get("media_keys") or [])
        if not keys:
            return
        key = keys[0]
        if key.endswith(self._VIDEO_EXTS):
            return
        try:
            path = self._object_store.resolve_path(key)
            data = await asyncio.to_thread(path.read_bytes)
        except Exception:  # noqa: BLE001
            logger.debug("media frame read failed %s", key, exc_info=True)
            return
        if not data or len(data) > 2_500_000:
            return
        mime = "jpeg"
        if key.endswith(".png"):
            mime = "png"
        elif key.endswith(".webp"):
            mime = "webp"
        elif key.endswith(".gif"):
            mime = "gif"
        handle = str(post.get("account_handle") or "")
        await self._emit(
            "screenshot",
            {
                "jpeg_b64": base64.b64encode(data).decode("ascii"),
                "mime": mime,
                "platform": platform,
                "url": next(
                    (t[5:] for t in post.get("theme_tags") or [] if t.startswith("link:")), ""
                ),
                "handle": handle,
                "label": f"{handle or post['external_post_id']} media",
            },
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


def _order_targets_for_engine(targets: list[ProfileTarget]) -> list[ProfileTarget]:
    """Stable reorder: on Obscura, HTTP OSS platforms before LinkedIn browser work."""
    if browser_engine() != "obscura" or len(targets) < 2:
        return list(targets)
    indexed = list(enumerate(targets))
    indexed.sort(
        key=lambda item: (
            _OBSCURA_SCOUT_PRIORITY.get(
                normalize_platform(item[1].platform or "web"),
                9,
            ),
            item[0],
        )
    )
    return [t for _, t in indexed]


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


def _post_permalink(post: RawPost, platform: str) -> str | None:
    platform = normalize_platform(platform)
    for tag in post.get("theme_tags") or []:
        if not str(tag).startswith("link:"):
            continue
        href = str(tag)[5:].strip()
        if not href.startswith("http"):
            continue
        low = href.lower()
        if platform == "linkedin" and (
            "/feed/update/" in low or "/posts/" in low or "activity:" in low
        ):
            return href
        if platform in {"x", "twitter"} and "/status/" in low:
            return href
        if platform == "instagram" and ("/p/" in low or "/reel/" in low or "/tv/" in low):
            return href
    return None


def _handle_for(target: ProfileTarget, url: str) -> str:
    raw = (target.handle or "").strip()
    if not raw:
        path = urlparse(url).path.strip("/")
        raw = path.split("/")[0] if path else urlparse(url).netloc
    raw = re.sub(r"[^\w.@-]+", ".", raw)[:80]
    if not raw.startswith("@"):
        raw = f"@{raw}"
    return raw[:100]
