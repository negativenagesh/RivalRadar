import asyncio
import contextlib
from collections.abc import AsyncIterator

from agent_events import AgentEventBus
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.agent_events_bus import get_event_bus
from app.clients import (
    fetch_ingestion_media,
    fetch_youtube_status,
    fetch_ingestion_accounts,
    fetch_ingestion_posts,
    fetch_ingestion_recording,
    fetch_ingestion_run,
    fetch_ingestion_screenshot,
    fetch_latest_digest,
    generate_creative_content,
    trigger_digest_generation,
    trigger_ingestion_run,
)
from app.db import get_session
from app.models import Draft, PipelineRun, PlatformConnection, ReviewState
from app.runs import create_pipeline_run, execute_pipeline_run
from app.schemas import (
    ConnectionStatusRead,
    ConnectionUpsert,
    DraftRead,
    EditRequest,
    PipelineRunCreated,
    PipelineRunRead,
)
from app.vault import encrypt_json

router = APIRouter()


@router.get("/digest/latest")
async def get_latest_digest() -> dict[str, object]:
    return await fetch_latest_digest()


@router.post("/digest/generate")
async def generate_digest() -> dict[str, object]:
    return await trigger_digest_generation()


@router.post("/drafts/generate", response_model=PipelineRunCreated, status_code=202)
async def generate_drafts(
    request: Request,
    session: AsyncSession = Depends(get_session),
    event_bus: AgentEventBus = Depends(get_event_bus),
) -> PipelineRunCreated:
    run = await create_pipeline_run(session)
    session_factory = getattr(request.app.state, "session_factory", None)
    asyncio.create_task(execute_pipeline_run(run.id, event_bus, session_factory=session_factory))
    return PipelineRunCreated(run_id=run.id, status=run.status)


@router.post("/creative/generate")
async def creative_generate(body: dict[str, object]) -> dict[str, object]:
    return await generate_creative_content(body)


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunRead)
async def get_pipeline_run(run_id: str, session: AsyncSession = Depends(get_session)) -> PipelineRun:
    run = await session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.websocket("/pipeline-runs/{run_id}/live")
async def pipeline_run_live_feed(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    event_bus = get_event_bus()
    try:
        async for event in event_bus.subscribe(run_id):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        return
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            with contextlib.suppress(RuntimeError):
                await websocket.close()


@router.post("/ingestion/runs")
async def start_ingestion_run(body: dict[str, object] | None = None) -> dict[str, object]:
    return await trigger_ingestion_run(body or {})


@router.get("/ingestion/runs/{run_id}")
async def get_ingestion_run(run_id: str) -> dict[str, object]:
    return await fetch_ingestion_run(run_id)


@router.websocket("/ingestion/runs/{run_id}/live")
async def ingestion_run_live_feed(websocket: WebSocket, run_id: str) -> None:
    """Live scout feed — same Redis stream ingestion publishes to."""
    await websocket.accept()
    event_bus = get_event_bus()
    try:
        async for event in event_bus.subscribe(run_id):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        return
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            with contextlib.suppress(RuntimeError):
                await websocket.close()


@router.get("/ingestion/runs/{run_id}/recording")
async def download_ingestion_recording(run_id: str) -> StreamingResponse:
    try:
        upstream = await fetch_ingestion_recording(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="No recording available for this run") from exc

    client = upstream.extensions.get("rivalradar_client")

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            if client is not None:
                await client.aclose()

    return StreamingResponse(
        stream(),
        media_type="video/webm",
        headers={"Content-Disposition": f'inline; filename="{run_id}.webm"'},
    )


@router.get("/ingestion/runs/{run_id}/screenshots/{index}")
async def download_ingestion_screenshot(run_id: str, index: int) -> StreamingResponse:
    try:
        upstream = await fetch_ingestion_screenshot(run_id, index)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Screenshot not found") from exc

    client = upstream.extensions.get("rivalradar_client")

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            if client is not None:
                await client.aclose()

    return StreamingResponse(stream(), media_type="image/jpeg")


@router.get("/ingestion/posts")
async def list_ingestion_posts() -> list[dict[str, object]]:
    return await fetch_ingestion_posts()


@router.get("/ingestion/accounts")
async def list_ingestion_accounts() -> list[dict[str, object]]:
    return await fetch_ingestion_accounts()


@router.get("/drafts", response_model=list[DraftRead])
async def list_drafts(session: AsyncSession = Depends(get_session)) -> list[Draft]:
    result = await session.scalars(select(Draft).order_by(Draft.created_at.desc()))
    return list(result.all())


async def _get_draft_or_404(session: AsyncSession, draft_id: str) -> Draft:
    draft = await session.get(Draft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


@router.post("/drafts/{draft_id}/approve", response_model=DraftRead)
async def approve_draft(draft_id: str, session: AsyncSession = Depends(get_session)) -> Draft:
    """Mark a draft ready-to-publish. A compliance failure doesn't block this
    endpoint -- the reviewer sees `compliance_passed`/`compliance_llm_reason`
    and can consciously override it; only human approval gates publishing,
    per spec.
    """
    draft = await _get_draft_or_404(session, draft_id)
    draft.review_state = ReviewState.READY_TO_PUBLISH
    await session.commit()
    await session.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/edit", response_model=DraftRead)
async def edit_draft(
    draft_id: str, request: EditRequest, session: AsyncSession = Depends(get_session)
) -> Draft:
    draft = await _get_draft_or_404(session, draft_id)
    draft.edited_caption = request.caption
    draft.review_state = ReviewState.EDITED
    await session.commit()
    await session.refresh(draft)
    return draft


@router.post("/drafts/{draft_id}/reject", response_model=DraftRead)
async def reject_draft(draft_id: str, session: AsyncSession = Depends(get_session)) -> Draft:
    draft = await _get_draft_or_404(session, draft_id)
    draft.review_state = ReviewState.REJECTED
    await session.commit()
    await session.refresh(draft)
    return draft



_KNOWN_PLATFORMS = [
    "youtube",
    "meta",
    "linkedin",
    "x",
    "tiktok",
    "threads",
    "instagram",
    "facebook",
]


@router.get("/connections", response_model=list[ConnectionStatusRead])
async def list_connections(
    workspace_id: str = "default",
    session: AsyncSession = Depends(get_session),
) -> list[ConnectionStatusRead]:
    rows = await session.scalars(
        select(PlatformConnection).where(PlatformConnection.workspace_id == workspace_id)
    )
    by_platform = {r.platform: r for r in rows.all()}

    youtube_detail = None
    try:
        yt = await fetch_youtube_status()
        youtube_detail = "API key ready" if yt.get("api_key_configured") else "Using yt-dlp fallback"
    except Exception:  # noqa: BLE001
        youtube_detail = "Ingestion unreachable"

    out: list[ConnectionStatusRead] = []
    for platform in _KNOWN_PLATFORMS:
        row = by_platform.get(platform)
        if platform == "youtube" and youtube_detail and "API key ready" in (youtube_detail or ""):
            out.append(
                ConnectionStatusRead(
                    platform=platform,
                    status="connected",
                    auth_type="api_key",
                    detail=youtube_detail,
                )
            )
            continue
        if row is None:
            out.append(
                ConnectionStatusRead(
                    platform=platform,
                    status="not_connected",
                    detail=youtube_detail if platform == "youtube" else None,
                )
            )
            continue
        status = row.status
        if row.expires_at is not None:
            from datetime import UTC, datetime

            if row.expires_at < datetime.now(UTC):
                status = "needs_reconnect"
        out.append(
            ConnectionStatusRead(
                platform=row.platform,
                status=status,  # type: ignore[arg-type]
                auth_type=row.auth_type,
                expires_at=row.expires_at,
                scopes=list(row.scopes or []),
                detail=None,
            )
        )
    return out


@router.get("/connections/{platform}", response_model=ConnectionStatusRead)
async def get_connection(
    platform: str,
    workspace_id: str = "default",
    session: AsyncSession = Depends(get_session),
) -> ConnectionStatusRead:
    platform = platform.lower()
    all_rows = await session.scalars(
        select(PlatformConnection).where(PlatformConnection.workspace_id == workspace_id)
    )
    row = next((r for r in all_rows.all() if r.platform == platform), None)
    if platform == "youtube":
        try:
            yt = await fetch_youtube_status()
            if yt.get("api_key_configured"):
                return ConnectionStatusRead(
                    platform=platform,
                    status="connected",
                    auth_type="api_key",
                    detail="API key ready",
                )
        except Exception:  # noqa: BLE001
            pass
    if row is None:
        return ConnectionStatusRead(platform=platform, status="not_connected")
    status = row.status
    if row.expires_at is not None:
        from datetime import UTC, datetime

        if row.expires_at < datetime.now(UTC):
            status = "needs_reconnect"
    return ConnectionStatusRead(
        platform=row.platform,
        status=status,  # type: ignore[arg-type]
        auth_type=row.auth_type,
        expires_at=row.expires_at,
        scopes=list(row.scopes or []),
    )



@router.post("/connections/{platform}", response_model=ConnectionStatusRead)
async def upsert_connection(
    platform: str,
    body: ConnectionUpsert,
    session: AsyncSession = Depends(get_session),
) -> ConnectionStatusRead:
    """Store encrypted OAuth token / cookie vault material — never passwords."""
    platform = platform.lower()
    if "password" in {k.lower() for k in body.secret.keys()}:
        raise HTTPException(status_code=400, detail="Passwords are not accepted — use OAuth or Connect session cookies")
    blob = encrypt_json(dict(body.secret))
    existing = await session.scalar(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == body.workspace_id,
            PlatformConnection.platform == platform,
        )
    )
    if existing is None:
        existing = PlatformConnection(
            workspace_id=body.workspace_id,
            platform=platform,
            auth_type=body.auth_type,
            encrypted_blob=blob,
            expires_at=body.expires_at,
            scopes=list(body.scopes),
            status="connected",
        )
        session.add(existing)
    else:
        existing.auth_type = body.auth_type
        existing.encrypted_blob = blob
        existing.expires_at = body.expires_at
        existing.scopes = list(body.scopes)
        existing.status = "connected"
    await session.commit()
    await session.refresh(existing)
    return ConnectionStatusRead(
        platform=existing.platform,
        status="connected",
        auth_type=existing.auth_type,
        expires_at=existing.expires_at,
        scopes=list(existing.scopes or []),
    )


@router.delete("/connections/{platform}", status_code=204)
async def delete_connection(
    platform: str,
    workspace_id: str = "default",
    session: AsyncSession = Depends(get_session),
) -> None:
    platform = platform.lower()
    row = await session.scalar(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == workspace_id,
            PlatformConnection.platform == platform,
        )
    )
    if row is not None:
        await session.delete(row)
        await session.commit()


@router.get("/ingestion/media/{media_key:path}")
async def download_ingestion_media(media_key: str) -> StreamingResponse:
    try:
        upstream = await fetch_ingestion_media(media_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Media not found") from exc

    client = upstream.extensions.get("rivalradar_client")

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            if client is not None:
                await client.aclose()

    content_type = upstream.headers.get("content-type", "application/octet-stream")
    return StreamingResponse(stream(), media_type=content_type)
