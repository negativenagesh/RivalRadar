from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.social_profile.browser import BrowserSession
from app.connectors.social_profile.extractors import build_raw_account, build_raw_post
from app.connectors.social_profile.targets import ProfileTarget

_AGENT_ID = "ingestion.browser"
_SERVICE = "ingestion"


class SocialProfileConnector:
    """Connector Protocol implementation backed by a live Playwright
    browser session.

    fetch_accounts/fetch_posts stay plain request/response, matching the
    Connector Protocol exactly (FixtureConnector's contract is unchanged).
    Live DOM/screenshot streaming is a side effect published onto the
    shared agent-events bus during the same run -- it never becomes part
    of the return value, so run_ingestion/ingest.py need no changes.

    One BrowserSession is shared across both fetch_accounts and
    fetch_posts (opened lazily on first use, closed via aclose) so a
    single recording covers the whole run rather than being overwritten
    between calls.
    """

    def __init__(
        self,
        run_id: str,
        targets: list[ProfileTarget],
        *,
        headless: bool = True,
        record: bool = False,
        event_bus: AgentEventBus | None = None,
        lookback_days: int = 3,
        human_pause: bool = True,
    ) -> None:
        self._run_id = run_id
        self._targets = targets
        self._headless = headless
        self._record = record
        self._event_bus = event_bus
        self._lookback_days = lookback_days
        self._human_pause = human_pause
        self._session: BrowserSession | None = None
        self._sequence = 0

    @property
    def recorded_video_path(self) -> Path | None:
        return self._session.recorded_video_path if self._session else None

    @property
    def sources_used(self) -> list[str]:
        return ["mock"]

    async def _ensure_session(self) -> BrowserSession:
        if self._session is None:
            self._session = await BrowserSession(
                headless=self._headless, record=self._record
            ).__aenter__()
        return self._session

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)

    async def _pause(self) -> None:
        if not self._human_pause:
            return
        delay = random.uniform(2.0, 4.0)
        await self._emit("action", {"detail": f"human_pause {delay:.1f}s"})
        await asyncio.sleep(delay)

    def _within_lookback(self, posted_at: str) -> bool:
        if not posted_at:
            return True
        try:
            posted = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        cutoff = datetime.now(UTC) - timedelta(days=self._lookback_days)
        return posted >= cutoff

    async def fetch_accounts(self) -> list[RawAccount]:
        session = await self._ensure_session()
        assert session.page is not None
        accounts: list[RawAccount] = []
        for target in self._targets:
            await self._emit("nav", {"url": target.url, "platform": target.platform})
            await session.page.goto(target.url, wait_until="domcontentloaded")
            await self._pause()
            frame = await session.screenshot_jpeg_b64()
            await self._emit(
                "screenshot",
                {
                    "jpeg_b64": frame,
                    "platform": target.platform,
                    "url": target.url,
                    "label": target.handle,
                },
            )

            header = session.page.locator(".profile-header")
            display_name = await session.page.locator(".profile-name").inner_text()
            platform = await header.get_attribute("data-platform") or target.platform
            accounts.append(
                build_raw_account(
                    handle=target.handle, display_name=display_name.strip(), platform=platform
                )
            )
            await self._emit("action", {"detail": "extracted account", "handle": target.handle})
        return accounts

    async def fetch_posts(self) -> list[RawPost]:
        session = await self._ensure_session()
        assert session.page is not None
        posts: list[RawPost] = []
        for target in self._targets:
            await self._emit("nav", {"url": target.url, "platform": target.platform})
            await session.page.goto(target.url, wait_until="domcontentloaded")
            await self._pause()
            await session.page.mouse.wheel(0, 600)
            await self._pause()
            frame = await session.screenshot_jpeg_b64()
            await self._emit(
                "screenshot",
                {
                    "jpeg_b64": frame,
                    "platform": target.platform,
                    "url": target.url,
                    "label": target.handle,
                },
            )

            cards = session.page.locator(".post-card")
            count = await cards.count()
            kept = 0
            for i in range(count):
                card = cards.nth(i)
                posted_at = await card.locator(".post-posted-at").get_attribute("datetime") or ""
                if not self._within_lookback(posted_at):
                    continue
                posts.append(
                    build_raw_post(
                        account_handle=target.handle,
                        external_post_id=await card.get_attribute("data-post-id") or "",
                        format=await card.get_attribute("data-format") or "",
                        theme_tags_csv=await card.locator(".post-themes").get_attribute(
                            "data-themes"
                        )
                        or "",
                        caption=(await card.locator(".post-caption").inner_text()).strip(),
                        image_url=await card.locator(".post-image").get_attribute("src"),
                        likes=await card.locator('[data-stat="likes"]').inner_text(),
                        comments=await card.locator('[data-stat="comments"]').inner_text(),
                        shares=await card.locator('[data-stat="shares"]').inner_text(),
                        posted_at=posted_at,
                    )
                )
                kept += 1
            await self._emit(
                "action",
                {
                    "detail": "extracted posts",
                    "handle": target.handle,
                    "count": kept,
                    "lookback_days": self._lookback_days,
                },
            )
        return posts

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

    async def _emit_screenshot(self) -> None:
        if self._event_bus is None or self._session is None:
            return
        frame = await self._session.screenshot_jpeg_b64()
        await self._emit("screenshot", {"jpeg_b64": frame})
