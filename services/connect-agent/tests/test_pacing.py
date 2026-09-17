"""Tests for Connect human-like pacing (random scroll + jitter timeouts)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from app.pacing import (
    ConnectPacingConfig,
    idle_presence_loop,
    jittered_pause,
    pacing_from_env,
    random_scroll,
    settle_after_load,
    settle_before_dump,
)


class FakeMouse:
    def __init__(self) -> None:
        self.wheels: list[tuple[int, int]] = []

    async def wheel(self, dx: int, dy: int) -> None:
        self.wheels.append((dx, dy))


class FakePage:
    def __init__(self, *, typing: bool = False) -> None:
        self.mouse = FakeMouse()
        self._typing = typing
        self.evaluate_calls = 0

    async def evaluate(self, _script: str) -> Any:
        self.evaluate_calls += 1
        return self._typing


@pytest.mark.asyncio
async def test_jittered_pause_sleeps_within_range(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("app.pacing.asyncio.sleep", _sleep)
    monkeypatch.setattr("app.pacing.random.uniform", lambda a, b: 2.5)
    got = await jittered_pause(1.0, 4.0, label="unit")
    assert got == 2.5
    assert slept == [2.5]


@pytest.mark.asyncio
async def test_random_scroll_wheels_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage(typing=False)
    monkeypatch.setattr("app.pacing.random.random", lambda: 0.0)
    # count=2, then two wheel deltas
    values = iter([2, 400, 400])
    monkeypatch.setattr("app.pacing.random.randint", lambda _a, _b: next(values))

    async def _sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.pacing.asyncio.sleep", _sleep)
    cfg = ConnectPacingConfig(
        enabled=True,
        scroll_probability=1.0,
        scroll_count=(2, 2),
        scroll_px=(400, 400),
        scroll_pause_s=(0.01, 0.01),
    )
    n = await random_scroll(page, cfg)  # type: ignore[arg-type]
    assert n == 2
    assert page.mouse.wheels == [(0, 400), (0, 400)]


@pytest.mark.asyncio
async def test_random_scroll_skips_when_typing(monkeypatch: pytest.MonkeyPatch) -> None:
    page = FakePage(typing=True)
    monkeypatch.setattr("app.pacing.random.random", lambda: 0.0)
    cfg = ConnectPacingConfig(enabled=True, scroll_probability=1.0)
    n = await random_scroll(page, cfg)  # type: ignore[arg-type]
    assert n == 0
    assert page.mouse.wheels == []


@pytest.mark.asyncio
async def test_settle_after_load_stretches_for_linkedin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[float, float, str]] = []

    async def fake_pause(min_s: float, max_s: float, *, label: str = "pause") -> float:
        calls.append((min_s, max_s, label))
        return min_s

    async def fake_scroll(_page: Any, _cfg: Any = None) -> int:
        return 0

    monkeypatch.setattr("app.pacing.jittered_pause", fake_pause)
    monkeypatch.setattr("app.pacing.random_scroll", fake_scroll)
    page = FakePage()
    cfg = ConnectPacingConfig(enabled=True, settle_min_s=1.0, settle_max_s=2.0)
    await settle_after_load(page, "linkedin", cfg)  # type: ignore[arg-type]
    assert calls
    assert calls[0][0] == pytest.approx(1.35)
    assert calls[0][1] == pytest.approx(2.7)
    assert "linkedin" in calls[0][2]


@pytest.mark.asyncio
async def test_settle_before_dump_can_disable(monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def boom(*_a: Any, **_k: Any) -> float:
        nonlocal called
        called = True
        return 0.0

    monkeypatch.setattr("app.pacing.jittered_pause", boom)
    await settle_before_dump(FakePage(), "x", ConnectPacingConfig(enabled=False))  # type: ignore[arg-type]
    assert called is False


@pytest.mark.asyncio
async def test_idle_presence_loop_stops_on_event(monkeypatch: pytest.MonkeyPatch) -> None:
    scrolls = 0

    async def fake_scroll(_page: Any, _cfg: Any = None) -> int:
        nonlocal scrolls
        scrolls += 1
        return 1

    monkeypatch.setattr("app.pacing.random_scroll", fake_scroll)
    monkeypatch.setattr("app.pacing.random.random", lambda: 0.0)
    monkeypatch.setattr(
        "app.pacing._typing_in_progress",
        lambda _p: asyncio.sleep(0, result=False),
    )
    stop = asyncio.Event()
    page = FakePage()
    cfg = ConnectPacingConfig(
        enabled=True,
        idle_min_s=0.01,
        idle_max_s=0.02,
        idle_scroll_probability=1.0,
    )
    task = asyncio.create_task(
        idle_presence_loop(page, "instagram", should_stop=stop, cfg=cfg)  # type: ignore[arg-type]
    )
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=1.0)
    assert scrolls >= 1


def test_pacing_from_env_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONNECT_HUMAN_PACING", "0")
    assert pacing_from_env().enabled is False


def test_sanitize_seed_cookies_filters_bad_rows() -> None:
    from app.browser import _sanitize_seed_cookies

    out = _sanitize_seed_cookies(
        [
            {"name": "sid", "value": "1", "domain": ".x.com"},
            {"name": "", "value": "nope"},
            {"foo": "bar"},
            SimpleNamespace(name="x"),  # type: ignore[list-item]
        ]
    )
    assert len(out) == 1
    assert out[0]["name"] == "sid"
    assert out[0]["domain"] == ".x.com"
