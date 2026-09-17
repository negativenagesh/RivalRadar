from __future__ import annotations

import asyncio
import threading
from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from app.connectors.base import Connector
from app.models import IngestionRun, RunStatus
from app.runs import (
    _RUN_WALL_S,
    _mark_run_budget_exceeded,
    _start_thread_watchdog,
)
from app.schemas import IngestionRunCreate, ProfileTargetIn
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class _Buf:
    _accounts: list[dict[str, str]] = [
        {"handle": "@x", "display_name": "x", "platform": "linkedin"}
    ]
    _posts: list[Any] = []
    sources_used: list[str] = ["browser"]


@pytest.mark.asyncio
async def test_mark_run_budget_exceeded_sets_error(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    run = IngestionRun(connector_type="auto", status=RunStatus.RUNNING)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    body = IngestionRunCreate(
        connector="auto",
        targets=[
            ProfileTargetIn(
                handle="pixisai",
                platform="linkedin",
                url="https://www.linkedin.com/company/pixisai",
            )
        ],
        lookback_days=7,
    )
    assert body.resolved_window().date_to >= date(2020, 1, 1)

    ok = await _mark_run_budget_exceeded(
        session_factory, run.id, body, cast(Connector, _Buf()), event_bus=None
    )
    assert ok is True
    updated = await session.get(IngestionRun, run.id)
    assert updated is not None
    assert updated.status == RunStatus.ERROR
    assert updated.error_detail is not None
    assert f"{int(_RUN_WALL_S)}" in updated.error_detail


@pytest.mark.asyncio
async def test_thread_watchdog_finalizes_run(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.runs._RUN_WALL_S", 0.2)
    # Force shared-factory path (own engine would be a different empty DB).
    monkeypatch.setattr("app.runs.settings.database_url", "sqlite+aiosqlite:///:memory:")

    run = IngestionRun(connector_type="auto", status=RunStatus.RUNNING)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    run_id = run.id

    body = IngestionRunCreate(connector="fixture", targets=[])
    bus = AsyncMock()
    bus.close_run = AsyncMock()
    stop = threading.Event()
    _start_thread_watchdog(
        loop=asyncio.get_running_loop(),
        factory=session_factory,
        run_id=run_id,
        body=body,
        connector=cast(Connector, _Buf()),
        event_bus=bus,
        stop=stop,
    )
    await asyncio.sleep(0.6)
    stop.set()

    updated = await session.get(IngestionRun, run_id)
    assert updated is not None
    assert updated.status == RunStatus.ERROR
    assert updated.error_detail is not None
    assert "run budget exceeded" in updated.error_detail


@pytest.mark.asyncio
async def test_sweep_orphaned_runs_marks_stale(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.runs import sweep_orphaned_runs

    stale = IngestionRun(connector_type="auto", status=RunStatus.RUNNING)
    session.add(stale)
    await session.commit()
    await session.refresh(stale)
    stale.created_at = datetime.now(UTC) - timedelta(seconds=500)
    await session.commit()
    run_id = stale.id

    n = await sweep_orphaned_runs(session_factory, older_than_s=180)
    assert n == 1
    updated = await session.get(IngestionRun, run_id)
    assert updated is not None
    assert updated.status == RunStatus.ERROR
    assert updated.error_detail is not None
    assert "orphaned" in updated.error_detail
