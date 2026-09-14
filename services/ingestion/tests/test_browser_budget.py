from __future__ import annotations

import asyncio
import time

import pytest
from app.connectors.social_profile.browser import await_or_abandon, chromium_args


def test_chromium_args_include_docker_sandbox_workarounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: False)
    headless = chromium_args(headless=True)
    assert "--no-sandbox" not in headless

    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: True)
    docker = chromium_args(headless=True)
    assert "--no-sandbox" in docker
    assert "--disable-dev-shm-usage" in docker


async def test_await_or_abandon_returns_before_hung_coro() -> None:
    started = time.monotonic()

    async def hung() -> None:
        await asyncio.sleep(60)

    with pytest.raises(TimeoutError, match="timed out"):
        await await_or_abandon(hung(), 0.15)
    elapsed = time.monotonic() - started
    assert elapsed < 2.0


async def test_await_or_abandon_returns_result() -> None:
    async def ok() -> str:
        await asyncio.sleep(0.01)
        return "pong"

    assert await await_or_abandon(ok(), 1.0) == "pong"
