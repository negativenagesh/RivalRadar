from __future__ import annotations

import uuid

from agent_events import AgentEventBus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.connectors.base import Connector
from app.connectors.fixture import FixtureConnector
from app.connectors.social_profile import ProfileTarget, SocialProfileConnector
from app.db import async_session_factory as default_session_factory
from app.ingest import run_ingestion
from app.models import IngestionRun, RunStatus
from app.objectstore import LocalDiskObjectStore, ObjectStore
from app.schemas import IngestionRunCreate

_MOCK_SITE_BASE_URL = "http://localhost:8000/mock-site/profile"


def _build_connector(run_id: str, body: IngestionRunCreate, event_bus: AgentEventBus) -> Connector:
    if body.connector == "fixture":
        return FixtureConnector()

    targets = [
        ProfileTarget(
            handle=t.handle,
            platform=t.platform,
            url=t.url or f"{_MOCK_SITE_BASE_URL}/{t.handle.lstrip('@')}",
        )
        for t in body.targets
    ]
    return SocialProfileConnector(
        run_id,
        targets,
        headless=body.headless,
        record=body.record,
        event_bus=event_bus,
    )


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
    """Runs in the background: performs ingestion, streams progress via
    event_bus, persists the final status/result, and archives any
    recording. Owns its own DB session since it outlives the request.

    session_factory defaults to the app's real engine-bound factory; tests
    inject an in-memory-sqlite-backed one so the background task and the
    test's assertions share the same database.
    """
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

        connector = _build_connector(run_id, body, event_bus)
        try:
            result = await run_ingestion(session, connector)
            recording_key = await _archive_recording(run_id, connector, store)

            run = await session.get(IngestionRun, run_id)
            assert run is not None
            run.status = RunStatus.DONE
            run.result = result.model_dump()
            run.recording_key = recording_key
            await session.commit()
            await event_bus.close_run(run_id, status="done")
        except Exception as exc:  # noqa: BLE001 - must record failure state either way
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
