from __future__ import annotations

import asyncio
import base64
import logging
import os
import tempfile
from collections.abc import Awaitable
from pathlib import Path
from types import TracebackType
from typing import Any, cast

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from app.connectors.session_cookies import sanitize_playwright_cookies

logger = logging.getLogger(__name__)

# Keep aligned with connect-agent so vaulted cookies look like the same browser.
CONNECT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
_LAUNCH_S = 25.0
_CLOSE_S = 8.0


def running_in_docker() -> bool:
    if os.environ.get("CONNECT_IN_DOCKER") == "1":
        return True
    return Path("/.dockerenv").exists()


def chromium_args(*, headless: bool = True) -> list[str]:
    """Docker Chromium needs no-sandbox + /dev/shm workarounds or launch hangs."""
    args = ["--disable-blink-features=AutomationControlled"]
    if running_in_docker() or not headless:
        args.extend(["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
    return args


def _chromium_args(*, headless: bool) -> list[str]:
    return chromium_args(headless=headless)


async def await_or_abandon[T](awaitable: Awaitable[T], seconds: float) -> T:
    """Wait up to `seconds`, then cancel and move on.

    asyncio.wait_for() waits for cancellation to finish. Playwright Chromium
    launch/goto often ignore CancelledError, which left scout stuck on oss_try.
    """
    task = asyncio.ensure_future(awaitable)
    done, _pending = await asyncio.wait({task}, timeout=seconds)
    if task in done:
        return task.result()
    task.cancel()
    await asyncio.wait({task}, timeout=min(_CLOSE_S, seconds))
    raise TimeoutError(f"timed out after {seconds:.0f}s")


class BrowserSession:
    """Owns one Playwright browser + context for the lifetime of an
    ingestion run. Recording (if requested) is Playwright's built-in
    per-context video capture -- written on context close, no extra deps.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        record: bool = False,
        cookies: list[dict[str, Any]] | None = None,
        storage_state: dict[str, Any] | None = None,
    ) -> None:
        self._headless = headless
        self._record = record
        self._cookies = cookies or []
        self._storage_state = storage_state
        self._video_dir: Path | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> BrowserSession:
        self._playwright = await await_or_abandon(async_playwright().start(), _LAUNCH_S)
        try:
            self._browser = await await_or_abandon(
                self._playwright.chromium.launch(
                    headless=self._headless,
                    args=_chromium_args(headless=self._headless),
                ),
                _LAUNCH_S,
            )
        except TimeoutError:
            await self._force_stop()
            raise RuntimeError("Chromium launch timed out") from None

        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": CONNECT_UA,
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
        }
        if self._storage_state:
            context_kwargs["storage_state"] = self._storage_state
        if self._record:
            self._video_dir = Path(tempfile.mkdtemp(prefix="rivalradar-rec-"))
            context_kwargs["record_video_dir"] = str(self._video_dir)
            context_kwargs["record_video_size"] = {"width": 1280, "height": 800}

        try:
            self._context = await await_or_abandon(
                self._browser.new_context(**context_kwargs), _LAUNCH_S
            )
            if not self._storage_state or self._cookies:
                await self._inject_cookies(self._cookies)
            self.page = await await_or_abandon(self._context.new_page(), _LAUNCH_S)
        except TimeoutError:
            await self._force_stop()
            raise RuntimeError("Chromium context timed out") from None
        return self

    async def _inject_cookies(self, cookies: list[dict[str, Any]]) -> None:
        assert self._context is not None
        cleaned = sanitize_playwright_cookies(cookies)
        if not cleaned:
            return
        try:
            await self._context.add_cookies(cast(Any, cleaned))
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("bulk add_cookies failed (%s); retrying one-by-one", exc)

        ok = 0
        for cookie in cleaned:
            try:
                await self._context.add_cookies(cast(Any, [cookie]))
                ok += 1
            except Exception:  # noqa: BLE001
                logger.debug("skipping invalid cookie %s", cookie.get("name"), exc_info=True)
        logger.info("injected %s/%s connect-session cookies", ok, len(cleaned))

    async def _force_stop(self) -> None:
        async def _quiet(coro: Awaitable[Any]) -> None:
            try:
                await await_or_abandon(coro, _CLOSE_S)
            except Exception:  # noqa: BLE001
                logger.debug("browser stop ignored", exc_info=True)

        if self._context is not None:
            await _quiet(self._context.close())
            self._context = None
        if self._browser is not None:
            await _quiet(self._browser.close())
            self._browser = None
        if self._playwright is not None:
            await _quiet(self._playwright.stop())
            self._playwright = None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        video_path: Path | None = None
        if self._context is not None:
            page_video = self.page.video if self.page else None
            try:
                await await_or_abandon(self._context.close(), _CLOSE_S)
            except Exception:  # noqa: BLE001
                logger.debug("context close ignored", exc_info=True)
            self._context = None
            if page_video is not None:
                try:
                    video_path = Path(await await_or_abandon(page_video.path(), _CLOSE_S))
                except Exception:  # noqa: BLE001
                    logger.debug("video path skipped", exc_info=True)
        await self._force_stop()
        self._recorded_video_path = video_path

    @property
    def recorded_video_path(self) -> Path | None:
        return getattr(self, "_recorded_video_path", None)

    async def screenshot_jpeg_b64(self) -> str:
        assert self.page is not None
        data = await self.page.screenshot(type="jpeg", quality=40)
        return base64.b64encode(data).decode("ascii")
