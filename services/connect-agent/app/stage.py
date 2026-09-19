"""Stage (never publish) a post in the live Connect / noVNC browser.

Mirrors ingestion stage_post selectors so LinkedIn / Instagram / X / YouTube
composers open with image + caption filled — operator hits Publish themselves.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os
import random
import tempfile
from typing import Any

from playwright.async_api import Locator, Page

logger = logging.getLogger(__name__)

_LINKEDIN_START = [
    "button:has-text('Start a post')",
    "[aria-label*='Start a post']",
]
_LINKEDIN_EDITOR = [
    "div.ql-editor[contenteditable='true']",
    "div[role='textbox'][contenteditable='true']",
]
_IMAGE_FILE_INPUTS = [
    "input[accept*='image']",
    "input[type='file']",
]
_INSTAGRAM_NEW_POST = [
    "[role='button']:has(svg[aria-label='New post'])",
    "[aria-label='New post']",
]
_INSTAGRAM_NEXT = [
    "div[role='button']:has-text('Next')",
]
_INSTAGRAM_CAPTION = [
    "textarea[aria-label*='caption' i]",
    "div[contenteditable='true'][aria-label*='caption' i]",
]
_YOUTUBE_TITLE = [
    "#textbox",
    "input#textbox",
    "div#textbox[contenteditable='true']",
    "ytcp-social-suggestions-textbox#title-textarea div#textbox",
]
_YOUTUBE_DESC = [
    "ytcp-social-suggestions-textbox#description-textarea div#textbox",
    "div#description-textarea div#textbox",
]
_YOUTUBE_FILE = [
    "input[type='file']",
    "input[type='file'][accept*='image']",
    "input[type='file'][accept*='video']",
]


class StageError(ValueError):
    pass


async def _pause(a: float = 1.0, b: float = 3.0) -> None:
    await asyncio.sleep(random.uniform(a, b))


async def _click_first(page: Page, selectors: list[str]) -> bool:
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            await loc.click(timeout=4000)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _set_image(page: Page, media_path: str) -> bool:
    for sel in _IMAGE_FILE_INPUTS:
        loc = page.locator(sel).first
        try:
            if await loc.count() == 0:
                continue
            await loc.set_input_files(media_path, timeout=5000)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


async def _fill_caption(page: Page, editor: Locator, caption: str, *, delay: int) -> None:
    try:
        await editor.click(timeout=4000)
        await editor.fill(caption, timeout=4000)
    except Exception:  # noqa: BLE001
        await editor.click(timeout=3000)
        await page.keyboard.type(caption, delay=delay)


async def _wait_first(page: Page, selectors: list[str]) -> Locator | None:
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            await loc.wait_for(state="visible", timeout=8000)
            return loc
        except Exception:  # noqa: BLE001
            continue
    return None


async def stage_linkedin(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=25_000)
    await _pause(2.0, 4.0)
    if not await _click_first(page, _LINKEDIN_START):
        raise StageError("could not find the LinkedIn composer — are you signed in?")
    await _pause(1.5, 3.0)
    editor = await _wait_first(page, _LINKEDIN_EDITOR)
    if editor is None:
        raise StageError("LinkedIn editor did not open")
    if media_path:
        await _set_image(page, media_path)
        await _pause(2.0, 5.0)
    await _fill_caption(page, editor, caption, delay=random.randint(30, 80))


async def stage_x(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25_000)
    await _pause(2.0, 4.0)
    composer = page.locator("div[data-testid='tweetTextarea_0']").first
    try:
        await composer.wait_for(state="visible", timeout=8000)
    except Exception as exc:  # noqa: BLE001
        raise StageError("X compose did not open — are you signed in?") from exc
    if media_path:
        file_input = page.locator("input[data-testid='fileInput']").first
        try:
            await file_input.set_input_files(media_path, timeout=5000)
        except Exception:  # noqa: BLE001
            await _set_image(page, media_path)
        await _pause(2.0, 5.0)
    await composer.click(timeout=4000)
    await page.keyboard.type(caption, delay=random.randint(25, 70))


async def stage_instagram(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=25_000)
    await _pause(2.0, 4.0)
    if not await _click_first(page, _INSTAGRAM_NEW_POST):
        raise StageError("could not find Instagram New post — are you signed in?")
    await _pause(1.5, 3.0)
    if media_path:
        if not await _set_image(page, media_path):
            raise StageError("could not attach image in Instagram composer")
        await _pause(2.0, 5.0)
    for _ in range(2):
        if not await _click_first(page, _INSTAGRAM_NEXT):
            break
        await _pause(1.5, 3.5)
    field = await _wait_first(page, _INSTAGRAM_CAPTION)
    if field is None:
        raise StageError("Instagram caption field not found")
    await _fill_caption(page, field, caption, delay=random.randint(30, 80))


async def stage_youtube(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://studio.youtube.com/", wait_until="domcontentloaded", timeout=30_000)
    await _pause(1.5, 3.0)
    opened = await _click_first(
        page,
        [
            "ytcp-button#create-icon",
            "#create-icon",
            "button[aria-label*='Create' i]",
            "tp-yt-paper-icon-button#create-icon",
        ],
    )
    if opened:
        await _pause(1.0, 2.0)
        await _click_first(
            page,
            [
                "tp-yt-paper-item:has-text('Upload videos')",
                "tp-yt-paper-item:has-text('Upload')",
                "ytcp-text-dropdown-trigger:has-text('Upload')",
            ],
        )
        await _pause(1.5, 3.0)
    if media_path and not await page.locator("input[type='file']").count():
        await page.goto(
            "https://www.youtube.com/upload",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await _pause(1.5, 3.0)
    if media_path:
        attached = await _set_image(page, media_path)
        if not attached:
            for sel in _YOUTUBE_FILE:
                loc = page.locator(sel).first
                try:
                    if await loc.count() == 0:
                        continue
                    await loc.set_input_files(media_path, timeout=5000)
                    attached = True
                    break
                except Exception:  # noqa: BLE001
                    continue
        await _pause(1.5, 3.0)
    parts = caption.strip().split("\n", 1)
    title = parts[0].strip()[:95] or "RivalRadar staged post"
    description = parts[1].strip() if len(parts) > 1 else caption.strip()
    title_field = await _wait_first(page, _YOUTUBE_TITLE)
    if title_field is not None:
        await _fill_caption(page, title_field, title, delay=15)
        await _pause(1.0, 2.0)
    desc_field = await _wait_first(page, _YOUTUBE_DESC)
    if desc_field is not None:
        await _fill_caption(page, desc_field, description[:5000], delay=12)


async def stage_on_platform(page: Page, platform: str, caption: str, media_path: str | None) -> None:
    plat = platform.lower().strip()
    if plat in {"twitter", "x"}:
        await stage_x(page, caption, media_path)
    elif plat == "linkedin":
        await stage_linkedin(page, caption, media_path)
    elif plat == "instagram":
        await stage_instagram(page, caption, media_path)
    elif plat == "youtube":
        await stage_youtube(page, caption, media_path)
    else:
        raise StageError(f"stage post not supported on {plat}")


async def run_stage(
    page: Page,
    *,
    platform: str,
    caption: str,
    media_png_b64: str | None,
) -> dict[str, Any]:
    media_path: str | None = None
    if media_png_b64:
        fd, media_path = tempfile.mkstemp(suffix=".png", prefix="rivalradar-stage-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(base64.b64decode(media_png_b64))
    try:
        await stage_on_platform(page, platform, caption.strip(), media_path)
        await _pause(1.5, 3.0)
        jpeg: str | None = None
        try:
            raw = await page.screenshot(type="jpeg", quality=70)
            jpeg = base64.b64encode(raw).decode("ascii")
        except Exception:  # noqa: BLE001
            logger.debug("stage screenshot failed", exc_info=True)
        return {
            "ok": True,
            "detail": f"staged in {platform} composer — review in noVNC and hit publish yourself",
            "screenshot_jpeg_b64": jpeg,
        }
    finally:
        if media_path:
            with contextlib.suppress(OSError):
                os.unlink(media_path)
