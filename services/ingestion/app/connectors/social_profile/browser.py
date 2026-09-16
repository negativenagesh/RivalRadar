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


def browser_engine() -> str:
    """obscura on Render/Docker; chromium for local/CI (unless overridden)."""
    raw = (os.environ.get("BROWSER_ENGINE") or "").strip().lower()
    if raw in {"obscura", "chromium"}:
        return raw
    if running_in_docker() or os.environ.get("RENDER"):
        return "obscura"
    return "chromium"


def obscura_cdp_url() -> str:
    return (os.environ.get("OBSCURA_CDP_URL") or "http://127.0.0.1:9222").rstrip("/")


def running_in_docker() -> bool:
    if os.environ.get("CONNECT_IN_DOCKER") == "1":
        return True
    return Path("/.dockerenv").exists()


def chromium_args(*, headless: bool = True) -> list[str]:
    """Docker Chromium needs no-sandbox + /dev/shm workarounds or launch hangs."""
    args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-features=TranslateUI",
        "--metrics-recording-only",
        "--safebrowsing-disable-auto-update",
    ]
    if running_in_docker() or not headless:
        args.extend(["--no-sandbox", "--disable-gpu"])
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
    ingestion run. Default engine is Obscura via CDP (light RAM on Render).
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
        self._owns_browser = True  # False when attached to shared Obscura CDP
        self.page: Page | None = None

    async def __aenter__(self) -> BrowserSession:
        self._playwright = await await_or_abandon(async_playwright().start(), _LAUNCH_S)
        engine = browser_engine()
        try:
            if engine == "obscura":
                await self._connect_obscura()
            else:
                await self._launch_chromium()
        except TimeoutError:
            await self._force_stop()
            raise RuntimeError(f"{engine} browser launch timed out") from None
        except Exception:
            await self._force_stop()
            raise

        return self

    async def _connect_obscura(self) -> None:
        assert self._playwright is not None
        cdp = obscura_cdp_url()
        logger.info("browser engine=obscura cdp=%s", cdp)
        self._browser = await await_or_abandon(
            self._playwright.chromium.connect_over_cdp(cdp),
            _LAUNCH_S,
        )
        self._owns_browser = False
        # Prefer an existing default context from obscura serve; else create one.
        if self._browser.contexts:
            self._context = self._browser.contexts[0]
        else:
            self._context = await await_or_abandon(
                self._browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=CONNECT_UA,
                    locale="en-US",
                ),
                _LAUNCH_S,
            )
        if self._cookies or self._storage_state:
            await self._inject_cookies(self._cookies)
        self.page = await await_or_abandon(self._context.new_page(), _LAUNCH_S)

    async def _launch_chromium(self) -> None:
        assert self._playwright is not None
        logger.info("browser engine=chromium")
        self._browser = await await_or_abandon(
            self._playwright.chromium.launch(
                headless=self._headless,
                args=_chromium_args(headless=self._headless),
            ),
            _LAUNCH_S,
        )
        self._owns_browser = True
        context_kwargs: dict[str, Any] = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": CONNECT_UA,
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
            "screen": {"width": 1280, "height": 900},
            "color_scheme": "light",
            "reduced_motion": "no-preference",
            "forced_colors": "none",
            "bypass_csp": False,
        }
        if self._storage_state:
            context_kwargs["storage_state"] = self._storage_state
        if self._record:
            self._video_dir = Path(tempfile.mkdtemp(prefix="rivalradar-rec-"))
            context_kwargs["record_video_dir"] = str(self._video_dir)
            context_kwargs["record_video_size"] = {"width": 1280, "height": 800}

        self._context = await await_or_abandon(
            self._browser.new_context(**context_kwargs), _LAUNCH_S
        )
        if not self._storage_state or self._cookies:
            await self._inject_cookies(self._cookies)
        self.page = await await_or_abandon(self._context.new_page(), _LAUNCH_S)

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

        # When attached to Obscura CDP, only close our page — leave the shared server up.
        if self.page is not None and not self._owns_browser:
            await _quiet(self.page.close())
            self.page = None
            self._context = None
            if self._browser is not None:
                await _quiet(self._browser.close())  # disconnect CDP client
                self._browser = None
        else:
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
        if self._owns_browser and self._context is not None:
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
        try:
            data = await self.page.screenshot(type="jpeg", quality=40)
            return base64.b64encode(data).decode("ascii")
        except Exception as exc:  # noqa: BLE001
            # Obscura may lack full compositor/screenshot; keep scout going.
            logger.warning("screenshot skipped (%s)", exc)
            return ""
