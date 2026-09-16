"""Human-like pacing + per-platform rate limiting for social actions.

This is for RELIABILITY and ACCOUNT SAFETY, not stealth. We space out actions
to respect platform rate limits and avoid triggering protective throttles.
All delays are logged so operators can audit behavior.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Per-platform hourly caps (conservative; LinkedIn is strictest)
PLATFORM_LIMITS: dict[str, int] = {
    "linkedin": 5,
    "x": 10,
    "instagram": 8,
    "youtube": 6,
    "tiktok": 6,
    "threads": 6,
}

# In-memory per-platform action timestamps (reset on process restart)
_LAST_ACTION: dict[str, float] = {}


@dataclass
class PacingConfig:
    """Jittered delays between browser actions to mimic human rhythm."""

    min_delay_s: float = 2.0
    max_delay_s: float = 5.0
    # Longer pause after risky actions (post, comment)
    action_min_s: float = 15.0
    action_max_s: float = 45.0
    # Random scroll simulation
    scroll_probability: float = 0.6
    scroll_duration_s: tuple[float, float] = (3.0, 8.0)


DEFAULT_PACING = PacingConfig()


async def jittered_pause(min_s: float = 2.0, max_s: float = 5.0, label: str = "pause") -> float:
    """Sleep for a random duration and log it. Returns actual seconds slept."""
    duration = random.uniform(min_s, max_s)
    logger.info("pacing: %s for %.1fs", label, duration)
    await asyncio.sleep(duration)
    return duration


async def action_pause(platform: str, cfg: PacingConfig = DEFAULT_PACING) -> None:
    """Pause after a risky action (post/comment) with platform-aware backoff."""
    duration = random.uniform(cfg.action_min_s, cfg.action_max_s)
    # LinkedIn gets extra caution
    if platform == "linkedin":
        duration *= 1.5
    logger.info("pacing: %s action cooldown %.1fs", platform, duration)
    await asyncio.sleep(duration)


async def random_scroll(page: Page, cfg: PacingConfig = DEFAULT_PACING) -> None:
    """Occasionally scroll the page to look like reading (not evasion)."""
    if random.random() > cfg.scroll_probability:
        return
    try:
        scrolls = random.randint(1, 3)
        for _ in range(scrolls):
            y = random.randint(300, 800)
            await page.mouse.wheel(0, y)
            await jittered_pause(*cfg.scroll_duration_s, label="scroll")
    except Exception as exc:  # noqa: BLE001
        logger.debug("scroll simulation skipped: %s", exc)


def check_rate_limit(platform: str) -> tuple[bool, float | None]:
    """Return (allowed, retry_after_seconds) based on last action timestamp."""
    limit = PLATFORM_LIMITS.get(platform, 10)
    last = _LAST_ACTION.get(platform)
    if last is None:
        return True, None
    elapsed = time.time() - last
    min_interval = 3600.0 / limit  # seconds between actions
    if elapsed >= min_interval:
        return True, None
    retry_after = min_interval - elapsed
    return False, retry_after


def record_action(platform: str) -> None:
    """Mark that an action just happened for rate limiting."""
    _LAST_ACTION[platform] = time.time()
    logger.info("pacing: recorded %s action at %.0f", platform, _LAST_ACTION[platform])


def reset_rate_limits() -> None:
    """For tests."""
    _LAST_ACTION.clear()
