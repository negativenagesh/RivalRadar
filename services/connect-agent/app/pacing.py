"""Human-like settle pacing for Connect (Playwright + noVNC login).

Mirrors ingestion Scout pacing (jittered pauses + occasional scroll) so the
headed Chromium session looks less robotic while the operator signs in via
noVNC. This is for account safety / natural rhythm — not stealth.

Auto-scroll stops once the page has focus on an input so typing is not
interrupted.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from dataclasses import dataclass

from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConnectPacingConfig:
    """Jittered delays after load and before cookie dump."""

    enabled: bool = True
    settle_min_s: float = 1.2
    settle_max_s: float = 3.5
    scroll_probability: float = 0.7
    scroll_count: tuple[int, int] = (1, 3)
    scroll_px: tuple[int, int] = (220, 720)
    scroll_pause_s: tuple[float, float] = (0.6, 1.8)
    # Background idle while awaiting_login (long gaps; skip if typing).
    idle_min_s: float = 12.0
    idle_max_s: float = 28.0
    idle_scroll_probability: float = 0.35


def pacing_from_env() -> ConnectPacingConfig:
    raw = (os.environ.get("CONNECT_HUMAN_PACING") or "1").strip().lower()
    enabled = raw not in {"0", "false", "off", "no"}
    return ConnectPacingConfig(enabled=enabled)


DEFAULT_PACING = ConnectPacingConfig()


async def jittered_pause(
    min_s: float,
    max_s: float,
    *,
    label: str = "pause",
) -> float:
    """Sleep a random duration and log it. Returns seconds slept."""
    lo, hi = (min_s, max_s) if min_s <= max_s else (max_s, min_s)
    duration = random.uniform(lo, hi)
    logger.info("connect-pacing: %s for %.1fs", label, duration)
    await asyncio.sleep(duration)
    return duration


async def _typing_in_progress(page: Page) -> bool:
    try:
        return bool(
            await page.evaluate(
                """() => {
                  const el = document.activeElement;
                  if (!el) return false;
                  const tag = (el.tagName || "").toLowerCase();
                  if (tag === "input" || tag === "textarea" || tag === "select") return true;
                  return !!el.isContentEditable;
                }"""
            )
        )
    except Exception:  # noqa: BLE001
        return False


async def random_scroll(page: Page, cfg: ConnectPacingConfig = DEFAULT_PACING) -> int:
    """Occasionally wheel-scroll like a human skimming the login page."""
    if not cfg.enabled or random.random() > cfg.scroll_probability:
        return 0
    if await _typing_in_progress(page):
        logger.debug("connect-pacing: skip scroll (input focused)")
        return 0
    scrolls = 0
    try:
        count = random.randint(*cfg.scroll_count)
        for _ in range(count):
            if await _typing_in_progress(page):
                break
            y = random.randint(*cfg.scroll_px)
            await page.mouse.wheel(0, y)
            scrolls += 1
            await jittered_pause(*cfg.scroll_pause_s, label="scroll")
    except Exception as exc:  # noqa: BLE001
        logger.debug("connect-pacing: scroll skipped: %s", exc)
    return scrolls


async def settle_after_load(
    page: Page,
    platform: str,
    cfg: ConnectPacingConfig | None = None,
) -> None:
    """Short human-like pause + scroll after opening the platform login URL."""
    cfg = cfg or pacing_from_env()
    if not cfg.enabled:
        return
    # LinkedIn / Instagram login pages are slower and more sensitive.
    stretch = 1.35 if platform in {"linkedin", "instagram"} else 1.0
    await jittered_pause(
        cfg.settle_min_s * stretch,
        cfg.settle_max_s * stretch,
        label=f"{platform} settle-after-load",
    )
    await random_scroll(page, cfg)


async def settle_before_dump(
    page: Page,
    platform: str,
    cfg: ConnectPacingConfig | None = None,
) -> None:
    """Brief pause before dumping cookies so the session looks settled."""
    cfg = cfg or pacing_from_env()
    if not cfg.enabled:
        return
    await jittered_pause(
        cfg.settle_min_s * 0.5,
        cfg.settle_max_s * 0.75,
        label=f"{platform} settle-before-dump",
    )
    await random_scroll(page, cfg)


async def idle_presence_loop(
    page: Page,
    platform: str,
    *,
    should_stop: asyncio.Event,
    cfg: ConnectPacingConfig | None = None,
) -> None:
    """Sparse background scrolls while awaiting login (never during typing)."""
    cfg = cfg or pacing_from_env()
    if not cfg.enabled:
        return
    while not should_stop.is_set():
        wait = random.uniform(cfg.idle_min_s, cfg.idle_max_s)
        try:
            await asyncio.wait_for(should_stop.wait(), timeout=wait)
            return
        except TimeoutError:
            pass
        if should_stop.is_set():
            return
        if random.random() > cfg.idle_scroll_probability:
            continue
        if await _typing_in_progress(page):
            continue
        logger.info("connect-pacing: %s idle presence scroll", platform)
        await random_scroll(
            page,
            ConnectPacingConfig(
                enabled=True,
                scroll_probability=1.0,
                scroll_count=(1, 2),
                scroll_px=cfg.scroll_px,
                scroll_pause_s=cfg.scroll_pause_s,
            ),
        )
