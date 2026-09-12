"""Headed browser sessions for platform Connect (login → dump cookies)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(minutes=15)


@dataclass
class LiveSession:
    session_id: str
    platform: str
    login_url: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "starting"
    detail: str | None = None
    playwright: Playwright | None = None
    browser: Browser | None = None
    context: BrowserContext | None = None
    page: Page | None = None

    @property
    def expired(self) -> bool:
        return datetime.now(UTC) > self.created_at + SESSION_TTL


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = asyncio.Lock()

    async def start(self, session_id: str, platform: str, login_url: str) -> LiveSession:
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                await self._close_unlocked(existing)
            live = LiveSession(session_id=session_id, platform=platform, login_url=login_url)
            self._sessions[session_id] = live

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()
            await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            live.playwright = playwright
            live.browser = browser
            live.context = context
            live.page = page
            live.status = "awaiting_login"
            live.detail = f"Sign in to {platform} in the opened browser, then confirm in RivalRadar"
        except Exception as exc:  # noqa: BLE001
            logger.exception("failed to start connect session %s", session_id)
            live.status = "error"
            live.detail = str(exc)
            await self.close(session_id)
            raise
        return live

    async def get(self, session_id: str) -> LiveSession | None:
        live = self._sessions.get(session_id)
        if live is None:
            return None
        if live.expired and live.status not in {"completed", "cancelled"}:
            live.status = "expired"
            live.detail = "Connect session timed out"
            await self.close(session_id)
            return live
        return live

    async def dump_cookies(self, session_id: str) -> list[dict[str, Any]]:
        live = await self.get(session_id)
        if live is None or live.context is None:
            raise KeyError(session_id)
        if live.status == "expired":
            raise RuntimeError("session expired")
        cookies = await live.context.cookies()
        return [dict(c) for c in cookies]

    async def close(self, session_id: str) -> None:
        async with self._lock:
            live = self._sessions.pop(session_id, None)
            if live is not None:
                await self._close_unlocked(live)

    async def _close_unlocked(self, live: LiveSession) -> None:
        for closer in (live.context, live.browser):
            if closer is None:
                continue
            try:
                await closer.close()
            except Exception:  # noqa: BLE001
                logger.debug("close failed for %s", live.session_id, exc_info=True)
        if live.playwright is not None:
            try:
                await live.playwright.stop()
            except Exception:  # noqa: BLE001
                logger.debug("playwright stop failed", exc_info=True)
        live.context = None
        live.browser = None
        live.page = None
        live.playwright = None


manager = SessionManager()
