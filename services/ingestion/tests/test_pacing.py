"""Tests for pacing and rate limiting."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from app.pacing import (
    DEFAULT_PACING,
    PLATFORM_LIMITS,
    action_pause,
    check_rate_limit,
    jittered_pause,
    random_scroll,
    record_action,
    reset_rate_limits,
)


@pytest.mark.asyncio
async def test_jittered_pause_within_bounds() -> None:
    start = asyncio.get_event_loop().time()
    duration = await jittered_pause(0.01, 0.05, label="test")
    elapsed = asyncio.get_event_loop().time() - start
    assert 0.01 <= duration <= 0.05
    assert elapsed >= 0.01


@pytest.mark.asyncio
async def test_action_pause_linkedin_longer() -> None:
    # LinkedIn gets 1.5x multiplier
    reset_rate_limits()
    start = asyncio.get_event_loop().time()
    await action_pause("linkedin")
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= DEFAULT_PACING.action_min_s * 1.5


def test_rate_limit_allows_first_action() -> None:
    reset_rate_limits()
    allowed, retry = check_rate_limit("linkedin")
    assert allowed is True
    assert retry is None


def test_rate_limit_blocks_rapid_repeat() -> None:
    reset_rate_limits()
    record_action("linkedin")
    allowed, retry = check_rate_limit("linkedin")
    assert allowed is False
    assert retry is not None
    assert retry > 0
    # Should be roughly 3600/limit seconds
    expected = 3600.0 / PLATFORM_LIMITS["linkedin"]
    assert abs(retry - expected) < 1.0


def test_rate_limit_allows_after_interval() -> None:
    reset_rate_limits()
    # Simulate old action
    import time

    from app.pacing import _LAST_ACTION

    _LAST_ACTION["x"] = time.time() - 400  # > 360s interval for 10/hour
    allowed, retry = check_rate_limit("x")
    assert allowed is True
    assert retry is None


@pytest.mark.asyncio
async def test_random_scroll_sometimes_skips() -> None:
    page = AsyncMock()
    page.mouse.wheel = AsyncMock()
    # Force scroll by mocking random
    import random

    original = random.random
    random.random = lambda: 0.0  # Always scroll
    try:
        await random_scroll(page)
        assert page.mouse.wheel.called
    finally:
        random.random = original
