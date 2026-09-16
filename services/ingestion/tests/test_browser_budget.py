from __future__ import annotations

import asyncio
import time

import pytest
from app.connectors.social_profile.browser import (
    await_or_abandon,
    browser_engine,
    chromium_args,
    obscura_cdp_url,
)


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


def test_browser_engine_defaults_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BROWSER_ENGINE", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: False)
    assert browser_engine() == "chromium"
    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: True)
    assert browser_engine() == "obscura"
    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: False)
    monkeypatch.setenv("RENDER", "true")
    assert browser_engine() == "obscura"
    monkeypatch.setenv("BROWSER_ENGINE", "chromium")
    assert browser_engine() == "chromium"
    monkeypatch.setenv("BROWSER_ENGINE", "weird")
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setattr("app.connectors.social_profile.browser.running_in_docker", lambda: False)
    assert browser_engine() == "chromium"


def test_obscura_cdp_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSCURA_CDP_URL", raising=False)
    assert obscura_cdp_url() == "ws://127.0.0.1:9222/devtools/browser"
    monkeypatch.setenv("OBSCURA_CDP_URL", "ws://127.0.0.1:9333/")
    assert obscura_cdp_url() == "ws://127.0.0.1:9333/devtools/browser"
    # Legacy http(s) env values are rewritten to ws(s) for Playwright.
    monkeypatch.setenv("OBSCURA_CDP_URL", "http://127.0.0.1:9333/")
    assert obscura_cdp_url() == "ws://127.0.0.1:9333/devtools/browser"
    monkeypatch.setenv("OBSCURA_CDP_URL", "https://cdp.example:9443")
    assert obscura_cdp_url() == "wss://cdp.example:9443/devtools/browser"
    # Full debugger path is left intact.
    monkeypatch.setenv("OBSCURA_CDP_URL", "ws://127.0.0.1:9222/devtools/browser")
    assert obscura_cdp_url() == "ws://127.0.0.1:9222/devtools/browser"


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
