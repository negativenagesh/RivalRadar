from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import uuid
from typing import Any

from agent_events import AgentEvent, AgentEventBus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.connectors.base import Connector
from app.connectors.composite import CompositeConnector
from app.connectors.fixture import FixtureConnector
from app.connectors.social_feed import SocialFeedConnector
from app.connectors.social_profile import ProfileTarget, SocialProfileConnector
from app.connectors.social_profile.browser import await_or_abandon
from app.connectors.web_url import WebUrlConnector
from app.connectors.youtube import YouTubeConnector
from app.db import async_session_factory as default_session_factory
from app.ingest import buffer_counts, persist_raw_buffers, run_ingestion
from app.models import IngestionRun, RunStatus
from app.objectstore import LocalDiskObjectStore, ObjectStore
from app.schemas import IngestionRunCreate, IngestionRunResult

logger = logging.getLogger(__name__)

_MOCK_SITE_BASE_URL = "http://localhost:8000/mock-site/profile"
_FEED_PLATFORMS = {"instagram", "linkedin", "x", "tiktok", "threads", "twitter", "facebook"}
# Hard wall so a wedged Playwright/CDP call cannot leave the run "running" forever.
_RUN_WALL_S = 180.0
_TERMINAL = {RunStatus.DONE, RunStatus.ERROR, RunStatus.CANCELLED}

# In-process registry so cancel can interrupt the asyncio task for a run.
_active_tasks: dict[str, asyncio.Task[Any]] = {}


def _wall_detail(*, accounts: int, posts: int) -> str:
    return (
        f"run budget exceeded after {_RUN_WALL_S:.0f}s (partial accounts={accounts} posts={posts})"
    )


async def _mark_run_budget_exceeded(
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    body: IngestionRunCreate,
    connector: Connector,
    event_bus: AgentEventBus | None = None,
) -> bool:
    """Finalize a wedged run on a fresh session (safe if scout still holds another)."""
    acc_n, post_n = buffer_counts(connector)
    window = body.resolved_window()
    detail = _wall_detail(accounts=acc_n, posts=post_n)
    result = IngestionRunResult(
        accounts_ingested=acc_n,
        posts_ingested=post_n,
        posts_skipped_duplicate=0,
        lookback_days=window.span_days,
        date_from=window.date_from.isoformat(),
        date_to=window.date_to.isoformat(),
        sources_used=list(getattr(connector, "sources_used", []) or []),
    ).model_dump()
    async with factory() as session:
        run = await session.get(IngestionRun, run_id)
        if run is None or run.status in _TERMINAL:
            return False
        run.status = RunStatus.ERROR
        run.error_detail = detail
        run.result = result
        await session.commit()
    if event_bus is not None:
        with contextlib.suppress(Exception):
            await event_bus.close_run(run_id, status="error", detail=detail)
    return True


def _start_thread_watchdog(
    *,
    loop: asyncio.AbstractEventLoop,
    factory: async_sessionmaker[AsyncSession],
    run_id: str,
    body: IngestionRunCreate,
    connector: Connector,
    event_bus: AgentEventBus,
    stop: threading.Event,
) -> threading.Thread:
    """Wall that still fires when the asyncio loop is blocked on CDP/Playwright.

    Uses a dedicated async engine inside ``asyncio.run`` so we never share the
    process engine across two event loops (undefined behavior with asyncpg).
    ``factory`` is only used as a fallback when DATABASE_URL is sqlite in-memory
    tests (shared fixture session).
    """

    def _watch() -> None:
        if stop.wait(_RUN_WALL_S):
            return
        logger.error("run %s thread watchdog fired after %.0fs", run_id, _RUN_WALL_S)
        task = get_active_run_task(run_id)
        if task is not None and not task.done():
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(task.cancel)

        async def _finalize() -> None:
            from sqlalchemy.ext.asyncio import async_sessionmaker as _asm
            from sqlalchemy.ext.asyncio import create_async_engine

            url = settings.database_url
            # In-memory sqlite fixtures must reuse the caller's factory/session.
            if ":memory:" in url or url.startswith("sqlite"):
                await _mark_run_budget_exceeded(factory, run_id, body, connector, event_bus)
                return
            engine = create_async_engine(
                url,
                echo=False,
                connect_args={"ssl": "require"} if settings.database_ssl else {},
            )
            own = _asm(engine, expire_on_commit=False)
            try:
                await _mark_run_budget_exceeded(own, run_id, body, connector, event_bus)
            finally:
                await engine.dispose()

        try:
            asyncio.run(_finalize())
        except Exception:  # noqa: BLE001
            logger.exception("thread watchdog failed to finalize run %s", run_id)

    thread = threading.Thread(target=_watch, name=f"run-wall-{run_id[:8]}", daemon=True)
    thread.start()
    return thread


def register_run_task(run_id: str, task: asyncio.Task[Any]) -> None:
    _active_tasks[run_id] = task

    def _clear(done: asyncio.Task[Any]) -> None:
        current = _active_tasks.get(run_id)
        if current is done:
            _active_tasks.pop(run_id, None)

    task.add_done_callback(_clear)


def get_active_run_task(run_id: str) -> asyncio.Task[Any] | None:
    return _active_tasks.get(run_id)


def _is_youtube_target(platform: str, url: str | None, handle: str) -> bool:
    blob = f"{platform} {url or ''} {handle}".lower()
    return "youtube" in blob or "youtu.be" in blob


def _has_http_url(url: str | None) -> bool:
    if not url:
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://") or "." in u


def _build_connector(
    run_id: str,
    body: IngestionRunCreate,
    event_bus: AgentEventBus,
    object_store: ObjectStore | None = None,
) -> Connector:
    if body.connector == "fixture":
        return FixtureConnector()

    youtube_targets: list[ProfileTarget] = []
    feed_targets: list[ProfileTarget] = []
    web_targets: list[ProfileTarget] = []
    mock_targets: list[ProfileTarget] = []

    for t in body.targets:
        if _is_youtube_target(t.platform, t.url, t.handle):
            youtube_targets.append(
                ProfileTarget(handle=t.handle, platform="youtube", url=t.url or t.handle)
            )
        elif t.platform == "mock" or (not _has_http_url(t.url) and t.platform in {"mock", ""}):
            mock_targets.append(
                ProfileTarget(
                    handle=t.handle,
                    platform=t.platform or "mock",
                    url=t.url or f"{_MOCK_SITE_BASE_URL}/{t.handle.lstrip('@')}",
                )
            )
        elif t.platform.lower() in _FEED_PLATFORMS or (
            _has_http_url(t.url)
            and any(
                p in (t.url or "").lower()
                for p in (
                    "instagram.com",
                    "linkedin.com",
                    "tiktok.com",
                    "threads.net",
                    "x.com",
                    "twitter.com",
                )
            )
        ):
            url = t.url or t.handle
            if not url.startswith("http"):
                url = f"https://{url}"
            platform = t.platform.lower() if t.platform else "web"
            if platform == "twitter":
                platform = "x"
            if "instagram.com" in url.lower():
                platform = "instagram"
            elif "linkedin.com" in url.lower():
                platform = "linkedin"
            elif "tiktok.com" in url.lower():
                platform = "tiktok"
            elif "threads.net" in url.lower():
                platform = "threads"
            elif "x.com" in url.lower() or "twitter.com" in url.lower():
                platform = "x"
            feed_targets.append(ProfileTarget(handle=t.handle, platform=platform, url=url))
        elif _has_http_url(t.url) or t.platform in {"web"}:
            url = t.url or t.handle
            if not url.startswith("http"):
                url = f"https://{url}"
            web_targets.append(
                ProfileTarget(handle=t.handle, platform=t.platform or "web", url=url)
            )
        else:
            mock_targets.append(
                ProfileTarget(
                    handle=t.handle,
                    platform=t.platform or "mock",
                    url=f"{_MOCK_SITE_BASE_URL}/{t.handle.lstrip('@')}",
                )
            )

    if (
        body.connector == "social_profile"
        and not youtube_targets
        and not feed_targets
        and not web_targets
        and not mock_targets
    ):
        mock_targets = [
            ProfileTarget(
                handle=t.handle,
                platform=t.platform,
                url=t.url or f"{_MOCK_SITE_BASE_URL}/{t.handle.lstrip('@')}",
            )
            for t in body.targets
        ]

    connectors: list[Connector] = []
    record_left = body.record
    window = body.resolved_window()

    if youtube_targets or body.connector == "youtube":
        targets = youtube_targets or [
            ProfileTarget(handle=t.handle, platform="youtube", url=t.url or t.handle)
            for t in body.targets
        ]
        connectors.append(
            YouTubeConnector(
                run_id,
                targets,
                window=window,
                api_key=settings.youtube_api_key,
                headless=body.headless,
                record=record_left and not feed_targets and not web_targets and not mock_targets,
                event_bus=event_bus,
                object_store=object_store,
            )
        )
        if record_left and not feed_targets and not web_targets and not mock_targets:
            record_left = False

    if feed_targets and body.connector != "youtube":
        connectors.append(
            SocialFeedConnector(
                run_id,
                feed_targets,
                window=window,
                headless=body.headless,
                record=record_left and not web_targets and not mock_targets,
                event_bus=event_bus,
                object_store=object_store,
                platform_sessions=body.platform_sessions,
            )
        )
        if record_left and not web_targets and not mock_targets:
            record_left = False

    if web_targets and body.connector != "youtube":
        connectors.append(
            WebUrlConnector(
                run_id,
                web_targets,
                lookback_days=body.lookback_days,
                headless=body.headless,
                record=record_left and not mock_targets,
                event_bus=event_bus,
                object_store_root=settings.object_store_root,
                platform_sessions=body.platform_sessions,
            )
        )
        if record_left and not mock_targets:
            record_left = False

    if mock_targets and body.connector != "youtube":
        connectors.append(
            SocialProfileConnector(
                run_id,
                mock_targets,
                headless=body.headless,
                record=record_left,
                event_bus=event_bus,
                lookback_days=body.lookback_days,
            )
        )

    if not connectors:
        return FixtureConnector()
    if len(connectors) == 1:
        return connectors[0]
    return CompositeConnector(connectors)


async def create_run(session: AsyncSession, body: IngestionRunCreate) -> IngestionRun:
    run = IngestionRun(
        id=str(uuid.uuid4()),
        connector_type=body.connector,
        status=RunStatus.PENDING,
        record=body.record,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def execute_run(
    run_id: str,
    body: IngestionRunCreate,
    event_bus: AgentEventBus,
    object_store: ObjectStore | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    store: ObjectStore
    if object_store is None:
        store = LocalDiskObjectStore(settings.object_store_root)
    else:
        store = object_store
    factory = session_factory or default_session_factory

    async with factory() as session:
        run = await session.get(IngestionRun, run_id)
        assert run is not None
        if run.status == RunStatus.CANCELLED:
            await event_bus.close_run(run_id, status="cancelled", detail="cancelled by operator")
            return
        run.status = RunStatus.RUNNING
        await session.commit()
        await event_bus.publish(
            AgentEvent(
                run_id=run_id,
                agent_id="ingestion",
                service="ingestion",
                step_type="status",
                payload={"status": "running"},
                sequence=0,
            )
        )

        connector = _build_connector(run_id, body, event_bus, object_store=store)

        async def _checkpoint() -> None:
            # Own session — scout must not share the run session with checkpoints
            # or a wall timeout will deadlock on AsyncSession.
            try:
                async with factory() as ckpt:
                    await persist_raw_buffers(ckpt, connector)
            except Exception:  # noqa: BLE001
                logger.exception("checkpoint persist failed for %s", run_id)

        for child in getattr(connector, "_connectors", None) or [connector]:
            setter = getattr(child, "set_checkpoint", None)
            if callable(setter):
                setter(_checkpoint)

        stop_watchdog = threading.Event()
        _start_thread_watchdog(
            loop=asyncio.get_running_loop(),
            factory=factory,
            run_id=run_id,
            body=body,
            connector=connector,
            event_bus=event_bus,
            stop=stop_watchdog,
        )

        try:
            try:
                result = await await_or_abandon(
                    run_ingestion(session, connector),
                    _RUN_WALL_S,
                )
            except TimeoutError:
                logger.error("run %s exceeded wall budget %.0fs", run_id, _RUN_WALL_S)
                with contextlib.suppress(Exception):
                    async with factory() as ckpt:
                        await persist_raw_buffers(ckpt, connector)
                await _mark_run_budget_exceeded(factory, run_id, body, connector, event_bus)
                return
            recording_key = await _archive_recording(run_id, connector, store)
            sources = list(
                getattr(connector, "sources_used", None)
                or getattr(connector, "sources_used", [])
                or []
            )
            shots = list(getattr(connector, "screenshot_keys", []) or [])
            window = body.resolved_window()
            acc_n, post_n = buffer_counts(connector)
            enriched = IngestionRunResult(
                accounts_ingested=acc_n or result.accounts_ingested,
                posts_ingested=post_n or result.posts_ingested,
                posts_skipped_duplicate=result.posts_skipped_duplicate,
                lookback_days=window.span_days,
                date_from=window.date_from.isoformat(),
                date_to=window.date_to.isoformat(),
                sources_used=sources,
            )
            payload = enriched.model_dump()
            payload["screenshots"] = shots

            run = await session.get(IngestionRun, run_id)
            assert run is not None
            if run.status in _TERMINAL:
                if run.status == RunStatus.CANCELLED:
                    await event_bus.close_run(
                        run_id, status="cancelled", detail="cancelled by operator"
                    )
                return
            run.status = RunStatus.DONE
            run.result = payload
            run.recording_key = recording_key
            await session.commit()
            await event_bus.close_run(run_id, status="done")
        except asyncio.CancelledError:
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001
                logger.debug("rollback after cancel failed", exc_info=True)
            persisted = 0
            try:
                async with factory() as ckpt:
                    persisted = await persist_raw_buffers(ckpt, connector)
                logger.info("persisted %s posts after cancel %s", persisted, run_id)
            except Exception:  # noqa: BLE001
                logger.exception("persist after cancel failed for %s", run_id)
            async with factory() as finish:
                run = await finish.get(IngestionRun, run_id)
                if run is not None and run.status not in _TERMINAL:
                    run.status = RunStatus.CANCELLED
                    run.error_detail = "cancelled by operator"
                    if persisted and not run.result:
                        window = body.resolved_window()
                        run.result = IngestionRunResult(
                            accounts_ingested=0,
                            posts_ingested=persisted,
                            posts_skipped_duplicate=0,
                            lookback_days=window.span_days,
                            date_from=window.date_from.isoformat(),
                            date_to=window.date_to.isoformat(),
                        ).model_dump()
                    await finish.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            async with factory() as finish:
                run = await finish.get(IngestionRun, run_id)
                assert run is not None
                if run.status in _TERMINAL:
                    if run.status == RunStatus.CANCELLED:
                        await event_bus.close_run(
                            run_id, status="cancelled", detail="cancelled by operator"
                        )
                    return
                run.status = RunStatus.ERROR
                run.error_detail = str(exc)
                await finish.commit()
            await event_bus.close_run(run_id, status="error", detail=str(exc))
        finally:
            stop_watchdog.set()


async def cancel_run(
    session: AsyncSession,
    run_id: str,
    event_bus: AgentEventBus,
) -> IngestionRun:
    """Mark a pending/running scout cancelled and interrupt its asyncio task if alive."""
    run = await session.get(IngestionRun, run_id)
    if run is None:
        raise KeyError(run_id)
    if run.status in {RunStatus.DONE, RunStatus.ERROR, RunStatus.CANCELLED}:
        return run

    run.status = RunStatus.CANCELLED
    run.error_detail = "cancelled by operator"
    await session.commit()
    await session.refresh(run)

    task = get_active_run_task(run_id)
    if task is not None and not task.done():
        task.cancel()

    await event_bus.close_run(run_id, status="cancelled", detail="cancelled by operator")
    return run


async def _archive_recording(
    run_id: str, connector: Connector, object_store: ObjectStore
) -> str | None:
    video_path = getattr(connector, "recorded_video_path", None)
    if video_path is None:
        return None
    key = f"recordings/{run_id}.webm"
    return await object_store.put(key, video_path)


async def list_runs(session: AsyncSession) -> list[IngestionRun]:
    result = await session.scalars(select(IngestionRun).order_by(IngestionRun.created_at.desc()))
    return list(result.all())
