from __future__ import annotations

import uuid

from agent_events import AgentEventBus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.connectors.base import Connector
from app.connectors.composite import CompositeConnector
from app.connectors.fixture import FixtureConnector
from app.connectors.social_profile import ProfileTarget, SocialProfileConnector
from app.connectors.web_url import WebUrlConnector
from app.connectors.youtube import YouTubeConnector
from app.db import async_session_factory as default_session_factory
from app.ingest import run_ingestion
from app.models import IngestionRun, RunStatus
from app.objectstore import LocalDiskObjectStore, ObjectStore
from app.schemas import IngestionRunCreate, IngestionRunResult

_MOCK_SITE_BASE_URL = "http://localhost:8000/mock-site/profile"


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
        elif _has_http_url(t.url) or t.platform in {
            "linkedin",
            "x",
            "instagram",
            "tiktok",
            "threads",
            "web",
        }:
            url = t.url or t.handle
            if not url.startswith("http"):
                url = f"https://{url}"
            web_targets.append(ProfileTarget(handle=t.handle, platform=t.platform, url=url))
        else:
            mock_targets.append(
                ProfileTarget(
                    handle=t.handle,
                    platform=t.platform or "mock",
                    url=f"{_MOCK_SITE_BASE_URL}/{t.handle.lstrip('@')}",
                )
            )

    if body.connector == "social_profile" and not youtube_targets and not web_targets and not mock_targets:
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

    if youtube_targets or body.connector == "youtube":
        targets = youtube_targets or [
            ProfileTarget(handle=t.handle, platform="youtube", url=t.url or t.handle)
            for t in body.targets
        ]
        connectors.append(
            YouTubeConnector(
                run_id,
                targets,
                window=body.resolved_window(),
                api_key=settings.youtube_api_key,
                headless=body.headless,
                record=record_left and not web_targets and not mock_targets,
                event_bus=event_bus,
                object_store=object_store,
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
        run.status = RunStatus.RUNNING
        await session.commit()

        connector = _build_connector(run_id, body, event_bus, object_store=store)
        try:
            result = await run_ingestion(session, connector)
            recording_key = await _archive_recording(run_id, connector, store)
            sources = list(getattr(connector, "sources_used", None) or getattr(connector, "sources_used", []) or [])
            shots = list(getattr(connector, "screenshot_keys", []) or [])
            window = body.resolved_window()
            enriched = IngestionRunResult(
                accounts_ingested=result.accounts_ingested,
                posts_ingested=result.posts_ingested,
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
            run.status = RunStatus.DONE
            run.result = payload
            run.recording_key = recording_key
            await session.commit()
            await event_bus.close_run(run_id, status="done")
        except Exception as exc:  # noqa: BLE001
            run = await session.get(IngestionRun, run_id)
            assert run is not None
            run.status = RunStatus.ERROR
            run.error_detail = str(exc)
            await session.commit()
            await event_bus.close_run(run_id, status="error", detail=str(exc))


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
