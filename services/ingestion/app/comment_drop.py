"""Approve-then-drop a single comment via the operator's Connect cookies."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from app.connectors.session_cookies import cookies_from_sessions, storage_state_from_sessions
from app.connectors.social_feed_parse import normalize_platform, settle_page
from app.connectors.social_profile.browser import BrowserSession

logger = logging.getLogger(__name__)

PAUSE_MIN_S = 10.0
PAUSE_MAX_S = 15.0
_ALLOWED = {"linkedin", "x", "instagram"}

_COMPOSERS: dict[str, list[str]] = {
    "linkedin": [
        "div.ql-editor[contenteditable='true']",
        "div[role='textbox'][contenteditable='true']",
        ".comments-comment-box-comment__text-editor",
    ],
    "x": [
        "div[data-testid='tweetTextarea_0']",
        "div[role='textbox'][data-testid='tweetTextarea_0']",
    ],
    "instagram": [
        "textarea[aria-label*='Add a comment']",
        "textarea[placeholder*='Add a comment']",
        "form textarea",
    ],
}

_SUBMIT: dict[str, list[str]] = {
    "linkedin": ["button.comments-comment-box__submit-button", "button[type='submit']"],
    "x": ["button[data-testid='tweetButton']", "button[data-testid='tweetButtonInline']"],
    "instagram": ["form button[type='submit']", "div[role='button']:has-text('Post')"],
}


class CommentDropError(ValueError):
    pass


async def human_pause() -> None:
    await asyncio.sleep(random.uniform(PAUSE_MIN_S, PAUSE_MAX_S))


def validate_drop(*, platform: str, url: str, text: str, approved: bool) -> str:
    if not approved:
        raise CommentDropError("human approval required")
    plat = normalize_platform(platform)
    if plat not in _ALLOWED:
        raise CommentDropError(f"comment drop not supported on {plat}")
    if not (url or "").startswith("http"):
        raise CommentDropError("permalink required")
    body = (text or "").strip()
    if not body:
        raise CommentDropError("comment text is empty")
    if len(body) > 500:
        raise CommentDropError("comment too long")
    return plat


async def drop_comment(
    *,
    platform: str,
    url: str,
    text: str,
    approved: bool,
    platform_sessions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plat = validate_drop(platform=platform, url=url, text=text, approved=approved)
    sessions = platform_sessions or {}
    cookies = cookies_from_sessions(sessions, platforms={plat, "twitter"} if plat == "x" else {plat})
    storage = storage_state_from_sessions(
        sessions, platforms={plat, "twitter"} if plat == "x" else {plat}
    )
    if not cookies and not storage:
        raise CommentDropError(f"not connected to {plat}")

    async with BrowserSession(headless=True, cookies=cookies, storage_state=storage) as session:
        assert session.page is not None
        page = session.page
        await page.goto(url, wait_until="domcontentloaded", timeout=25_000)
        await settle_page(page, quiet_ms=200)
        await human_pause()
        filled = False
        for sel in _COMPOSERS[plat]:
            loc = page.locator(sel).first
            try:
                if await loc.count() == 0:
                    continue
                await loc.click(timeout=4000)
                await loc.fill(text.strip(), timeout=4000)
                filled = True
                break
            except Exception:  # noqa: BLE001
                try:
                    await loc.click(timeout=3000)
                    await page.keyboard.type(text.strip(), delay=40)
                    filled = True
                    break
                except Exception:  # noqa: BLE001
                    continue
        if not filled:
            raise CommentDropError("could not find a comment composer on this post")
        await human_pause()
        submitted = False
        for sel in _SUBMIT[plat]:
            loc = page.locator(sel).first
            try:
                if await loc.count() == 0:
                    continue
                await loc.click(timeout=4000)
                submitted = True
                break
            except Exception:  # noqa: BLE001
                continue
        if not submitted:
            await page.keyboard.press("Enter")
        jpeg = await session.screenshot_jpeg_b64()
        return {
            "ok": True,
            "detail": f"dropped on {plat}",
            "screenshot_jpeg_b64": jpeg,
        }
