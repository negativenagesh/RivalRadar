from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from types import TracebackType

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright


class BrowserSession:
    """Owns one Playwright browser + context for the lifetime of an
    ingestion run. Recording (if requested) is Playwright's built-in
    per-context video capture -- written on context close, no extra deps.
    """

    def __init__(self, *, headless: bool = True, record: bool = False) -> None:
        self._headless = headless
        self._record = record
        self._video_dir: Path | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> BrowserSession:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)

        if self._record:
            self._video_dir = Path(tempfile.mkdtemp(prefix="rivalradar-rec-"))
            self._context = await self._browser.new_context(
                record_video_dir=str(self._video_dir),
                record_video_size={"width": 1280, "height": 800},
            )
        else:
            self._context = await self._browser.new_context()
        self.page = await self._context.new_page()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        video_path: Path | None = None
        if self._context is not None:
            page_video = self.page.video if self.page else None
            await self._context.close()
            if page_video is not None:
                video_path = Path(await page_video.path())
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._recorded_video_path = video_path

    @property
    def recorded_video_path(self) -> Path | None:
        return getattr(self, "_recorded_video_path", None)

    async def screenshot_jpeg_b64(self) -> str:
        assert self.page is not None
        data = await self.page.screenshot(type="jpeg", quality=40)
        return base64.b64encode(data).decode("ascii")
