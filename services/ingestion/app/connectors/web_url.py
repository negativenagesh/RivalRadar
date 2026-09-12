"""Visit arbitrary public social/profile URLs with Playwright.

Used for LinkedIn / X / IG / TikTok / Threads / websites when Context
provides a link. Login walls still get a screenshot + page title parse;
structured feed posts are best-effort from meta/OG tags.
"""

from __future__ import annotations

import asyncio
import base64
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.social_profile.browser import BrowserSession
from app.connectors.social_profile.targets import ProfileTarget

_AGENT_ID = "ingestion.webscout"
_SERVICE = "ingestion"


class WebUrlConnector:
    def __init__(
        self,
        run_id: str,
        targets: list[ProfileTarget],
        *,
        lookback_days: int = 3,
        headless: bool = True,
        record: bool = False,
        event_bus: AgentEventBus | None = None,
        human_pause: bool = True,
        object_store_root: str | None = None,
    ) -> None:
        self._run_id = run_id
        self._targets = targets
        self._lookback_days = lookback_days
        self._headless = headless
        self._record = record
        self._event_bus = event_bus
        self._human_pause = human_pause
        self._object_store_root = object_store_root
        self._session: BrowserSession | None = None
        self._sequence = 0
        self._accounts: list[RawAccount] = []
        self._posts: list[RawPost] = []
        self._screenshot_keys: list[str] = []
        self._loaded = False

    @property
    def recorded_video_path(self) -> Path | None:
        return self._session.recorded_video_path if self._session else None

    @property
    def sources_used(self) -> list[str]:
        return ["browser"]

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
        self._session = await BrowserSession(
            headless=self._headless, record=self._record
        ).__aenter__()
        assert self._session.page is not None
        for i, target in enumerate(self._targets):
            await self._scout_one(target, index=i)
        self._loaded = True

    async def _pause(self) -> None:
        if not self._human_pause:
            return
        delay = random.uniform(2.0, 4.0)
        await self._emit("action", {"detail": f"human_pause {delay:.1f}s"})
        await asyncio.sleep(delay)

    async def _scout_one(self, target: ProfileTarget, *, index: int) -> None:
        assert self._session is not None and self._session.page is not None
        url = target.url or target.handle
        if not url.startswith("http"):
            url = f"https://{url}"

        await self._emit("nav", {"url": url, "platform": target.platform})
        try:
            await self._session.page.goto(url, wait_until="domcontentloaded", timeout=45000)
        except Exception as exc:  # noqa: BLE001 - keep run alive across flaky hosts
            await self._emit("error", {"detail": f"nav failed {url}: {exc}"})
            # Still create a stub account so Findings show the attempt
            handle = _handle_for(target, url)
            self._accounts.append(
                RawAccount(
                    handle=handle,
                    display_name=target.handle or handle,
                    platform=target.platform or "web",
                )
            )
            return

        await self._pause()
        await self._session.page.mouse.wheel(0, 800)
        await self._pause()

        jpeg_b64 = await self._session.screenshot_jpeg_b64()
        await self._emit(
            "screenshot",
            {
                "jpeg_b64": jpeg_b64,
                "platform": target.platform,
                "url": url,
                "label": target.handle,
            },
        )
        key = await self._persist_screenshot(jpeg_b64, index)
        if key:
            self._screenshot_keys.append(key)

        title = await self._session.page.title()
        og_desc = await self._meta("og:description") or await self._meta("description")
        og_image = await self._meta("og:image")
        handle = _handle_for(target, url)
        display = (title or handle).strip()[:200] or handle

        self._accounts.append(
            RawAccount(handle=handle, display_name=display[:200], platform=target.platform or "web")
        )

        caption_parts = [display]
        if og_desc:
            caption_parts.append(og_desc[:500])
        caption_parts.append(f"Source: {url}")
        posted = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        themes = [
            target.platform or "web",
            "source:browser",
            f"lookback:{self._lookback_days}",
            f"link:{url[:180]}",
        ]
        if key:
            themes.append(f"shot:{key}")

        self._posts.append(
            RawPost(
                account_handle=handle,
                external_post_id=f"web-{self._run_id[:8]}-{target.platform}-{index}",
                format="founder_post",
                theme_tags=themes,
                caption="\n\n".join(caption_parts),
                image_url=og_image or (f"/ingestion/runs/{self._run_id}/screenshots/{index}" if key else None),
                likes=0,
                comments=0,
                shares=0,
                posted_at=posted,
            )
        )
        await self._emit(
            "action",
            {
                "detail": "parsed page",
                "platform": target.platform,
                "title": display[:80],
            },
        )

    async def _meta(self, name: str) -> str | None:
        assert self._session is not None and self._session.page is not None
        loc = self._session.page.locator(
            f'meta[property="{name}"], meta[name="{name}"]'
        ).first
        try:
            if await loc.count() == 0:
                return None
            return await loc.get_attribute("content")
        except Exception:  # noqa: BLE001
            return None

    async def _persist_screenshot(self, jpeg_b64: str, index: int) -> str | None:
        if not self._object_store_root:
            return None
        root = Path(self._object_store_root)
        key = f"screenshots/{self._run_id}/{index}.jpg"
        dest = root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(jpeg_b64))
        return key

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
    raw = target.handle.strip() or urlparse(url).path.strip("/") or urlparse(url).netloc
    raw = re.sub(r"[^\w.@-]+", ".", raw)[:80]
    if not raw.startswith("@"):
        raw = f"@{raw}" if not raw.startswith("http") else f"@{urlparse(url).netloc}"
    return raw[:100]
