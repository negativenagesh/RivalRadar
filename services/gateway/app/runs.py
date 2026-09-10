from __future__ import annotations

import uuid

from agent_events import AgentEventBus
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients import fetch_latest_digest
from app.db import async_session_factory as default_session_factory
from app.models import PipelineRun, PipelineRunStatus
from app.pipeline import generate_drafts_from_digest


async def create_pipeline_run(session: AsyncSession) -> PipelineRun:
    run = PipelineRun(id=str(uuid.uuid4()), status=PipelineRunStatus.PENDING)
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def execute_pipeline_run(
    run_id: str,
    event_bus: AgentEventBus,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Runs in the background: fetches the latest digest, generates a draft
    per cluster (streaming progress via event_bus), and persists the final
    run status. Owns its own DB session since it outlives the request."""
    factory = session_factory or default_session_factory

    async with factory() as session:
        run = await session.get(PipelineRun, run_id)
        assert run is not None
        run.status = PipelineRunStatus.RUNNING
        await session.commit()

        try:
            digest = await fetch_latest_digest()
            drafts = await generate_drafts_from_digest(
                session, digest, run_id=run_id, event_bus=event_bus
            )

            run = await session.get(PipelineRun, run_id)
            assert run is not None
            run.status = PipelineRunStatus.DONE
            run.digest_id = digest["id"]
            run.draft_ids = [d.id for d in drafts]
            await session.commit()
            await event_bus.close_run(run_id, status="done")
        except Exception as exc:  # noqa: BLE001 - must record failure state either way
            run = await session.get(PipelineRun, run_id)
            assert run is not None
            run.status = PipelineRunStatus.ERROR
            run.error_detail = str(exc)
            await session.commit()
            await event_bus.close_run(run_id, status="error", detail=str(exc))
