import asyncio

from agent_events import AgentEventBus
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.agent_events_bus import get_event_bus
from app.config import settings
from app.db import get_session
from app.models import CompetitorAccount, CompetitorPost, IngestionRun
from app.objectstore import LocalDiskObjectStore
from app.runs import create_run, execute_run, list_runs
from app.schemas import (
    CompetitorAccountRead,
    CompetitorPostRead,
    IngestionRunCreate,
    IngestionRunCreated,
    IngestionRunRead,
)

router = APIRouter()


@router.post("/ingest/run", response_model=IngestionRunCreated, status_code=202)
async def trigger_ingestion(
    request: Request,
    body: IngestionRunCreate = IngestionRunCreate(),
    session: AsyncSession = Depends(get_session),
    event_bus: AgentEventBus = Depends(get_event_bus),
) -> IngestionRunCreated:
    run = await create_run(session, body)
    session_factory = getattr(request.app.state, "session_factory", None)
    asyncio.create_task(execute_run(run.id, body, event_bus, session_factory=session_factory))
    return IngestionRunCreated(run_id=run.id, status=run.status)


@router.get("/ingest/runs", response_model=list[IngestionRunRead])
async def get_runs(session: AsyncSession = Depends(get_session)) -> list[IngestionRun]:
    return await list_runs(session)


@router.get("/ingest/runs/{run_id}", response_model=IngestionRunRead)
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> IngestionRun:
    run = await session.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/ingest/runs/{run_id}/recording")
async def download_recording(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    run = await session.get(IngestionRun, run_id)
    if run is None or run.recording_key is None:
        raise HTTPException(status_code=404, detail="No recording available for this run")

    object_store = LocalDiskObjectStore(settings.object_store_root)
    return StreamingResponse(
        object_store.open(run.recording_key),
        media_type="video/webm",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.webm"'},
    )


@router.websocket("/ingest/runs/{run_id}/live")
async def run_live_feed(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    event_bus = get_event_bus()
    try:
        async for event in event_bus.subscribe(run_id):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        return
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()


@router.get("/accounts", response_model=list[CompetitorAccountRead])
async def list_accounts(
    session: AsyncSession = Depends(get_session),
) -> list[CompetitorAccount]:
    result = await session.scalars(select(CompetitorAccount))
    return list(result.all())


@router.get("/posts", response_model=list[CompetitorPostRead])
async def list_posts(session: AsyncSession = Depends(get_session)) -> list[CompetitorPost]:
    result = await session.scalars(select(CompetitorPost))
    return list(result.all())
