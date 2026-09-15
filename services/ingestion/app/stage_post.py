"""Stage (never publish) an image post via the operator's Connect cookies.

Opens the platform composer with the vaulted session, attaches the
generated image, fills the caption, and stops short of the final
Post/Share/Tweet button, returning a screenshot as proof.
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

from app.connectors.session_cookies import cookies_from_sessions, storage_state_from_sessions
from app.connectors.social_feed_parse import normalize_platform, settle_page
from app.connectors.social_profile.browser import BrowserSession

logger = logging.getLogger(__name__)

STAGE_PAUSE_MIN_S = 1.0
STAGE_PAUSE_MAX_S = 3.0
_ALLOWED = {"linkedin", "x", "instagram"}
_MAX_CAPTION = 3000

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


class StagePostError(ValueError):
    pass


async def stage_pause() -> None:
    await asyncio.sleep(random.uniform(STAGE_PAUSE_MIN_S, STAGE_PAUSE_MAX_S))


def validate_stage(*, platform: str, caption: str, approved: bool) -> str:
    if not approved:
        raise StagePostError("human approval required")
    plat = normalize_platform(platform)
    if plat == "youtube":
        raise StagePostError("youtube staging not supported for image posts")
    if plat not in _ALLOWED:
        raise StagePostError(f"stage post not supported on {plat}")
    body = (caption or "").strip()
    if not body:
        raise StagePostError("caption is empty")
    if len(body) > _MAX_CAPTION:
        raise StagePostError("caption too long")
    return plat


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


async def _stage_linkedin(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=25_000)
    await settle_page(page, quiet_ms=200)
    await stage_pause()
    if not await _click_first(page, _LINKEDIN_START):
        raise StagePostError("could not find the linkedin composer")
    editor = await _wait_first(page, _LINKEDIN_EDITOR)
    if editor is None:
        raise StagePostError("linkedin editor did not open")
    if media_path:
        await _set_image(page, media_path)
        await stage_pause()
    await _fill_caption(page, editor, caption, delay=20)


async def _stage_x(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25_000)
    await settle_page(page, quiet_ms=200)
    await stage_pause()
    composer = page.locator("div[data-testid='tweetTextarea_0']").first
    try:
        await composer.wait_for(state="visible", timeout=8000)
    except Exception as exc:  # noqa: BLE001
        raise StagePostError("x composer did not open") from exc
    if media_path:
        file_input = page.locator("input[data-testid='fileInput']").first
        try:
            await file_input.set_input_files(media_path, timeout=5000)
        except Exception:  # noqa: BLE001
            await _set_image(page, media_path)
        await stage_pause()
    await composer.click(timeout=4000)
    await page.keyboard.type(caption, delay=15)


async def _stage_instagram(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=25_000)
    await settle_page(page, quiet_ms=200)
    await stage_pause()
    if not await _click_first(page, _INSTAGRAM_NEW_POST):
        raise StagePostError("could not find the instagram new-post button")
    if media_path:
        if not await _set_image(page, media_path):
            raise StagePostError("could not attach image in instagram composer")
        await stage_pause()
    for _ in range(2):
        if not await _click_first(page, _INSTAGRAM_NEXT):
            break
        await stage_pause()
    field = await _wait_first(page, _INSTAGRAM_CAPTION)
    if field is None:
        raise StagePostError("instagram caption field not found")
    await _fill_caption(page, field, caption, delay=20)


async def _stage_on_platform(
    page: Page, plat: str, caption: str, media_path: str | None
) -> None:
    if plat == "linkedin":
        await _stage_linkedin(page, caption, media_path)
    elif plat == "x":
        await _stage_x(page, caption, media_path)
    else:
        await _stage_instagram(page, caption, media_path)


async def stage_post(
    *,
    platform: str,
    caption: str,
    media_png_b64: str | None,
    approved: bool,
    platform_sessions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plat = validate_stage(platform=platform, caption=caption, approved=approved)
    sessions = platform_sessions or {}
    cookies = cookies_from_sessions(sessions, platforms={plat, "twitter"} if plat == "x" else {plat})
    storage = storage_state_from_sessions(
        sessions, platforms={plat, "twitter"} if plat == "x" else {plat}
    )
    if not cookies and not storage:
        raise StagePostError(f"not connected to {plat}")

    text = caption.strip()
    media_path: str | None = None
    if media_png_b64:
        fd, media_path = tempfile.mkstemp(suffix=".png", prefix="rivalradar-stage-")
        with os.fdopen(fd, "wb") as fh:
            fh.write(base64.b64decode(media_png_b64))
    try:
        async with BrowserSession(headless=True, cookies=cookies, storage_state=storage) as session:
            assert session.page is not None
            page = session.page
            try:
                await _stage_on_platform(page, plat, text, media_path)
            except StagePostError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise StagePostError(f"could not stage on {plat}: {exc}") from exc
            await stage_pause()
            # Deliberately stop here: never click Post / Share / Tweet.
            jpeg = await session.screenshot_jpeg_b64()
            return {
                "ok": True,
                "detail": f"staged in {plat} composer",
                "screenshot_jpeg_b64": jpeg,
            }
    finally:
        if media_path:
            with contextlib.suppress(OSError):
                os.unlink(media_path)
