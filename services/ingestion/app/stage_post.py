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
from app.pacing import action_pause, check_rate_limit, jittered_pause, random_scroll, record_action

logger = logging.getLogger(__name__)

STAGE_PAUSE_MIN_S = 1.0
STAGE_PAUSE_MAX_S = 3.0
_ALLOWED = {"linkedin", "x", "instagram", "youtube"}
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


class RateLimitError(StagePostError):
    def __init__(self, platform: str, retry_after: float) -> None:
        super().__init__(
            f"{platform} rate limited — wait {int(retry_after)}s before next action. "
            "This protects your account from platform throttles."
        )
        self.retry_after = retry_after


async def stage_pause() -> None:
    await asyncio.sleep(random.uniform(STAGE_PAUSE_MIN_S, STAGE_PAUSE_MAX_S))


def validate_stage(*, platform: str, caption: str, approved: bool) -> str:
    if not approved:
        raise StagePostError("human approval required")
    plat = normalize_platform(platform)
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
    await jittered_pause(2.0, 4.0, label="linkedin feed load")
    await random_scroll(page)
    if not await _click_first(page, _LINKEDIN_START):
        raise StagePostError("could not find the linkedin composer")
    await jittered_pause(1.5, 3.0, label="linkedin composer open")
    editor = await _wait_first(page, _LINKEDIN_EDITOR)
    if editor is None:
        raise StagePostError("linkedin editor did not open")
    if media_path:
        await _set_image(page, media_path)
        await jittered_pause(2.0, 5.0, label="linkedin image attach")
    await _fill_caption(page, editor, caption, delay=random.randint(30, 80))


async def _stage_x(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25_000)
    await settle_page(page, quiet_ms=200)
    await jittered_pause(2.0, 4.0, label="x compose load")
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
        await jittered_pause(2.0, 5.0, label="x image attach")
    await composer.click(timeout=4000)
    await page.keyboard.type(caption, delay=random.randint(25, 70))


async def _stage_instagram(page: Page, caption: str, media_path: str | None) -> None:
    await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=25_000)
    await settle_page(page, quiet_ms=200)
    await jittered_pause(2.0, 4.0, label="instagram home load")
    await random_scroll(page)
    if not await _click_first(page, _INSTAGRAM_NEW_POST):
        raise StagePostError("could not find the instagram new-post button")
    await jittered_pause(1.5, 3.0, label="instagram composer open")
    if media_path:
        if not await _set_image(page, media_path):
            raise StagePostError("could not attach image in instagram composer")
        await jittered_pause(2.0, 5.0, label="instagram image attach")
    for _ in range(2):
        if not await _click_first(page, _INSTAGRAM_NEXT):
            break
        await jittered_pause(1.5, 3.5, label="instagram next")
    field = await _wait_first(page, _INSTAGRAM_CAPTION)
    if field is None:
        raise StagePostError("instagram caption field not found")
    await _fill_caption(page, field, caption, delay=random.randint(30, 80))



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


async def _stage_youtube(page: Page, caption: str, media_path: str | None) -> None:
    """Open YouTube Studio upload drawer, fill title/description, stop before Publish."""
    await page.goto(
        "https://studio.youtube.com/",
        wait_until="domcontentloaded",
        timeout=30_000,
    )
    await settle_page(page, quiet_ms=250)
    await stage_pause()
    # Create → Upload videos (button labels vary by locale).
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
        await stage_pause()
        await _click_first(
            page,
            [
                "tp-yt-paper-item:has-text('Upload videos')",
                "tp-yt-paper-item:has-text('Upload')",
                "ytcp-text-dropdown-trigger:has-text('Upload')",
            ],
        )
        await stage_pause()
    # Direct upload URL fallback.
    if media_path and not await page.locator("input[type='file']").count():
        await page.goto(
            "https://www.youtube.com/upload",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        await settle_page(page, quiet_ms=200)
        await stage_pause()
    if media_path:
        # Image attaches as community/custom thumbnail when the dialog allows file pickers.
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
        await stage_pause()
    parts = caption.strip().split("\n", 1)
    title = parts[0].strip()[:95] or "RivalRadar staged post"
    description = parts[1].strip() if len(parts) > 1 else caption.strip()
    title_field = await _wait_first(page, _YOUTUBE_TITLE)
    if title_field is not None:
        await _fill_caption(page, title_field, title, delay=15)
        await stage_pause()
    desc_field = await _wait_first(page, _YOUTUBE_DESC)
    if desc_field is not None:
        await _fill_caption(page, desc_field, description[:5000], delay=12)
    # Never click Next/Publish — leave the upload/details draft open.


async def _stage_on_platform(
    page: Page, plat: str, caption: str, media_path: str | None
) -> None:
    if plat == "linkedin":
        await _stage_linkedin(page, caption, media_path)
    elif plat == "x":
        await _stage_x(page, caption, media_path)
    elif plat == "youtube":
        await _stage_youtube(page, caption, media_path)
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

    # Rate limit check (protects account from platform throttles)
    allowed, retry_after = check_rate_limit(plat)
    if not allowed:
        raise RateLimitError(plat, retry_after or 60.0)

    sessions = platform_sessions or {}
    cookie_plats = {plat, "twitter"} if plat == "x" else {plat, "google"} if plat == "youtube" else {plat}
    cookies = cookies_from_sessions(sessions, platforms=cookie_plats)
    storage = storage_state_from_sessions(
        sessions, platforms=cookie_plats
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
                # Simulate reading the composed post before staging
                await random_scroll(page)
                await jittered_pause(3.0, 6.0, label="review post")
            except StagePostError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise StagePostError(f"could not stage on {plat}: {exc}") from exc
            record_action(plat)
            await action_pause(plat)
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
