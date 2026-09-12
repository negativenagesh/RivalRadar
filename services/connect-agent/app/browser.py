"""Headed browser sessions for platform Connect (login → dump cookies).

Uses a persistent Chromium profile per platform under PROFILE_ROOT so logins
survive reconnect. Vaulted cookies/storage_state are also re-seeded when present.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

logger = logging.getLogger(__name__)

SESSION_TTL = timedelta(minutes=30)

CONNECT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

PROFILE_ROOT = Path(os.environ.get("CONNECT_PROFILE_ROOT", "/data/profiles"))


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
    persistent: bool = False

    @property
    def expired(self) -> bool:
        return datetime.now(UTC) > self.created_at + SESSION_TTL


def _chromium_args() -> list[str]:
    args = ["--disable-blink-features=AutomationControlled"]
    if os.environ.get("DISPLAY") or os.environ.get("CONNECT_IN_DOCKER") == "1":
        args.extend(
            [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
    return args


def _safe_platform_dir(platform: str) -> Path:
    cleaned = re.sub(r"[^a-z0-9_-]+", "_", platform.lower()).strip("_") or "web"
    path = PROFILE_ROOT / cleaned
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_seed_cookies(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        value = item.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or not name:
            continue
        cookie: dict[str, Any] = {
            "name": name,
            "value": value,
            "path": item.get("path") or "/",
        }
        domain = item.get("domain")
        if isinstance(domain, str) and domain:
            cookie["domain"] = domain
        url = item.get("url")
        if isinstance(url, str) and url.startswith("http") and "domain" not in cookie:
            cookie["url"] = url
        for flag in ("httpOnly", "secure", "sameSite"):
            if flag in item:
                cookie[flag] = item[flag]
        expires = item.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            cookie["expires"] = float(expires)
        if "domain" in cookie or "url" in cookie:
            out.append(cookie)
    return out


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, LiveSession] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        session_id: str,
        platform: str,
        login_url: str,
        *,
        cookies: list[dict[str, Any]] | None = None,
        storage_state: dict[str, Any] | None = None,
    ) -> LiveSession:
        async with self._lock:
            existing = self._sessions.get(session_id)
            if existing is not None:
                await self._close_unlocked(existing)
            live = LiveSession(session_id=session_id, platform=platform, login_url=login_url)
            self._sessions[session_id] = live

        seeded = False
        try:
            playwright = await async_playwright().start()
            profile_dir = _safe_platform_dir(platform)
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=_chromium_args(),
                viewport={"width": 1280, "height": 900},
                user_agent=CONNECT_UA,
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )
            live.persistent = True
            live.playwright = playwright
            live.browser = context.browser
            live.context = context

            seed_cookies = _sanitize_seed_cookies(cookies)
            if storage_state and isinstance(storage_state, dict):
                # Prefer explicit cookie list from storage_state when provided.
                state_cookies = storage_state.get("cookies")
                if isinstance(state_cookies, list) and not seed_cookies:
                    seed_cookies = _sanitize_seed_cookies(
                        [c for c in state_cookies if isinstance(c, dict)]
                    )
            if seed_cookies:
                try:
                    await context.add_cookies(seed_cookies)  # type: ignore[arg-type]
                    seeded = True
                except Exception:  # noqa: BLE001
                    logger.warning("failed to seed vault cookies for %s", platform, exc_info=True)

            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            live.page = page
            live.status = "awaiting_login"
            viewer = (os.environ.get("PUBLIC_VIEWER_URL") or "").strip()
            if seeded or profile_dir.exists():
                live.detail = (
                    f"Reusing saved {platform} session — confirm you're signed in "
                    f"(or finish login), then click I've logged in"
                    + (f". Viewer: {viewer}" if viewer else "")
                )
            elif viewer:
                live.detail = (
                    f"Sign in to {platform} in the Connect browser tab ({viewer}), "
                    "then confirm in RivalRadar"
                )
            else:
                live.detail = (
                    f"Sign in to {platform} in the opened browser, then confirm in RivalRadar"
                )
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

    async def dump_session(self, session_id: str) -> dict[str, Any]:
        live = await self.get(session_id)
        if live is None or live.context is None:
            raise KeyError(session_id)
        if live.status == "expired":
            raise RuntimeError("session expired")
        cookies = [dict(c) for c in await live.context.cookies()]
        storage_state: dict[str, Any] | None = None
        try:
            storage_state = await live.context.storage_state()
        except Exception:  # noqa: BLE001
            logger.debug("storage_state dump failed", exc_info=True)
        return {"cookies": cookies, "storage_state": storage_state}

    async def dump_cookies(self, session_id: str) -> list[dict[str, Any]]:
        payload = await self.dump_session(session_id)
        cookies = payload.get("cookies")
        return cookies if isinstance(cookies, list) else []

    async def close(self, session_id: str) -> None:
        async with self._lock:
            live = self._sessions.pop(session_id, None)
            if live is not None:
                await self._close_unlocked(live)

    async def _close_unlocked(self, live: LiveSession) -> None:
        # Persistent profile stays on disk — only close the live context.
        if live.context is not None:
            try:
                await live.context.close()
            except Exception:  # noqa: BLE001
                logger.debug("context close failed for %s", live.session_id, exc_info=True)
        elif live.browser is not None:
            try:
                await live.browser.close()
            except Exception:  # noqa: BLE001
                logger.debug("browser close failed for %s", live.session_id, exc_info=True)
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
