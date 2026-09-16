import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator

from agent_events import AgentEventBus
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.agent_events_bus import get_event_bus
from app.clients import (
    cancel_ingestion_run,
    drop_ingestion_comment,
    fetch_ingestion_accounts,
    fetch_ingestion_media,
    fetch_ingestion_posts,
    fetch_ingestion_recording,
    fetch_ingestion_run,
    fetch_ingestion_screenshot,
    fetch_latest_digest,
    fetch_youtube_status,
    generate_creative_content,
    generate_intel_report,
    generate_publish_plan,
    ping_generation_vendor,
    stage_ingestion_post,
    stream_comment_draft,
    stream_intel_report,
    stream_publish_plan,
    trigger_digest_generation,
    trigger_ingestion_run,
)
from app.config import settings
from app.connect_agent import (
    ConnectAgentError,
    agent_close_session,
    agent_dump_session,
    agent_health,
    agent_start_session,
    public_viewer_url,
)
from app.connect_sessions import (
    ConnectSession,
    connect_open_url,
    expires_at_from_cookies,
    pop_session,
    put_session,
)
from app.connect_sessions import (
    get_session as get_connect_session,
)
from app.db import get_session
from app.models import Draft, PipelineRun, PlatformConnection, ReviewState
from app.quick_connect import (
    PLATFORM_COOKIE_SPEC,
    consume_pairing_code,
    issue_pairing_code,
    normalize_cookies,
    probe_session,
)
from app.runs import create_pipeline_run, execute_pipeline_run
from app.schemas import (
    ConnectionStatusRead,
    ConnectionUpsert,
    ConnectSessionRead,
    ConnectSessionStart,
    DraftRead,
    EditRequest,
    PairingCodeRead,
    PairingCodeRequest,
    PipelineRunCreated,
    PipelineRunRead,
    QuickConnectRequest,
)
from app.vault import decrypt_json, encrypt_json
from app.ws_proxy import ingestion_live_upstream_url, proxy_client_to_upstream

logger = logging.getLogger(__name__)

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


def _operator_headers(
    x_gemini_key: str | None,
    x_deepseek_key: str | None = None,
    x_nvidia_key: str | None = None,
    x_agnes_key: str | None = None,
    x_text_model: str | None = None,
    x_image_model: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    gemini = (x_gemini_key or "").strip()
    deepseek = (x_deepseek_key or "").strip()
    nvidia = (x_nvidia_key or "").strip()
    agnes = (x_agnes_key or "").strip()
    text = (x_text_model or "").strip()
    image = (x_image_model or "").strip()
    if gemini:
        headers["X-Gemini-Key"] = gemini
    if deepseek:
        headers["X-DeepSeek-Key"] = deepseek
    if nvidia:
        headers["X-Nvidia-Key"] = nvidia
    if agnes:
        headers["X-Agnes-Key"] = agnes
    if text:
        headers["X-Text-Model"] = text.lower()
    if image:
        headers["X-Image-Model"] = image.lower()
    # Empty is fine: generation falls back to server env keys (gpt-oss / Agnes defaults).
    return headers


def _platform_aliases(platform: str) -> set[str]:
    plat = platform.lower().strip()
    if plat in {"x", "twitter"}:
        return {"x", "twitter"}
    return {plat}


async def _vaulted_sessions(
    session: AsyncSession,
    *,
    workspace_id: str = "default",
    platforms: set[str] | None = None,
) -> dict[str, object]:
    from app.vault_sessions import load_vaulted_platform_sessions

    loaded = await load_vaulted_platform_sessions(
        session, workspace_id=workspace_id, platforms=platforms
    )
    return {k: v for k, v in loaded.items()}


@router.get("/models/defaults")
async def model_defaults() -> dict[str, object]:
    from app.clients import fetch_model_defaults

    result: dict[str, object] = await fetch_model_defaults()
    return result


@router.post("/creative/generate")
async def creative_generate(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> dict[str, object]:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    return await generate_creative_content(body, operator_headers=headers)


@router.post("/intel/report")
async def intel_report(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> dict[str, object]:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    return await generate_intel_report(body, operator_headers=headers)


@router.post("/intel/report/stream")
async def intel_report_stream(
    request: Request,
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> StreamingResponse:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    body: dict[str, object] = await request.json()
    return StreamingResponse(
        stream_intel_report(body, operator_headers=headers),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/llm/ping")
async def llm_ping(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
) -> dict[str, object]:
    vendor = str(body.get("vendor") or "").strip().lower()
    keep = {
        "gemini": "X-Gemini-Key",
        "deepseek": "X-DeepSeek-Key",
        "nvidia": "X-Nvidia-Key",
        "agnes": "X-Agnes-Key",
    }.get(vendor)
    if not keep:
        raise HTTPException(
            status_code=400, detail="Vendor must be gemini, deepseek, nvidia, or agnes."
        )
    ping_headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
    )
    if keep not in ping_headers:
        raise HTTPException(status_code=400, detail=f"Paste your {vendor} API key to test it.")
    return await ping_generation_vendor(
        {"vendor": vendor}, operator_headers={keep: ping_headers[keep]}
    )


@router.post("/social/comment")
async def social_comment(
    body: dict[str, object],
    session: AsyncSession = Depends(get_session),
    workspace_id: str = "default",
) -> dict[str, object]:
    if not body.get("approved"):
        raise HTTPException(status_code=400, detail="human approval required")
    platform = str(body.get("platform") or "").strip()
    url = str(body.get("url") or "").strip()
    text = str(body.get("text") or "").strip()
    aliases = _platform_aliases(platform)
    vault = await _vaulted_sessions(session, workspace_id=workspace_id, platforms=aliases)
    if not vault:
        raise HTTPException(
            status_code=400, detail=f"not connected to {platform or 'this platform'}"
        )
    payload = {
        "platform": platform,
        "url": url,
        "text": text,
        "approved": True,
        "platform_sessions": vault,
    }
    return await drop_ingestion_comment(payload)


@router.post("/creative/publish-plan")
async def creative_publish_plan(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> dict[str, object]:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    return await generate_publish_plan(body, operator_headers=headers)


@router.post("/creative/publish-plan/stream")
async def creative_publish_plan_stream(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> StreamingResponse:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    return StreamingResponse(
        stream_publish_plan(body, operator_headers=headers),
        media_type="text/event-stream",
    )


@router.post("/creative/comment/stream")
async def creative_comment_stream(
    body: dict[str, object],
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> StreamingResponse:
    headers = _operator_headers(
        x_gemini_key,
        x_deepseek_key=x_deepseek_key,
        x_nvidia_key=x_nvidia_key,
        x_agnes_key=x_agnes_key,
        x_text_model=x_text_model,
        x_image_model=x_image_model,
    )
    return StreamingResponse(
        stream_comment_draft(body, operator_headers=headers),
        media_type="text/event-stream",
    )


@router.post("/social/stage-post")
async def social_stage_post(
    body: dict[str, object],
    session: AsyncSession = Depends(get_session),
    workspace_id: str = "default",
) -> dict[str, object]:
    if not body.get("approved"):
        raise HTTPException(status_code=400, detail="human approval required")
    platform = str(body.get("platform") or "").strip()
    caption = str(body.get("caption") or "").strip()
    aliases = _platform_aliases(platform)
    vault = await _vaulted_sessions(session, workspace_id=workspace_id, platforms=aliases)
    if not vault:
        raise HTTPException(
            status_code=400, detail=f"not connected to {platform or 'this platform'}"
        )
    payload = {
        "platform": platform,
        "caption": caption,
        "media_png_b64": body.get("media_png_b64"),
        "approved": True,
        "platform_sessions": vault,
    }
    return await stage_ingestion_post(payload)


@router.get("/pipeline-runs/{run_id}", response_model=PipelineRunRead)
async def get_pipeline_run(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> PipelineRun:
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
async def start_ingestion_run(
    body: dict[str, object] | None = None,
    workspace_id: str = "default",
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """Start Scout with Connect-extension vault cookies attached automatically."""
    payload = dict(body or {})
    platform_sessions = await _vaulted_sessions(session, workspace_id=workspace_id)
    if platform_sessions:
        payload["platform_sessions"] = platform_sessions
    return await trigger_ingestion_run(payload)


@router.get("/ingestion/runs/{run_id}")
async def get_ingestion_run(run_id: str) -> dict[str, object]:
    return await fetch_ingestion_run(run_id)


@router.post("/ingestion/runs/{run_id}/cancel")
async def cancel_ingestion_run_route(run_id: str) -> dict[str, object]:
    try:
        return await cancel_ingestion_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc


@router.websocket("/ingestion/runs/{run_id}/live")
async def ingestion_run_live_feed(websocket: WebSocket, run_id: str) -> None:
    """Live scout feed.

    Prefer proxying to ingestion's WS — events are published there. With
    REDIS_URL=memory, gateway FakeRedis never sees those events.
    Falls back to the local bus when the upstream is unreachable (tests /
    shared Redis still works via subscribe).
    """
    await websocket.accept()
    upstream = ingestion_live_upstream_url(settings.ingestion_service_url, run_id)
    try:
        await proxy_client_to_upstream(websocket, upstream)
        return
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("ingestion live proxy failed (%s); falling back to local bus", exc)

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


@router.get("/ingestion/youtube/status")
async def ingestion_youtube_status() -> dict[str, object]:
    """Proxy ingestion's yt-dlp / Data API readiness (Connect center + deploy checks)."""
    try:
        return await fetch_youtube_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail="Ingestion YouTube status unreachable") from exc


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
        youtube_detail = (
            "API key ready" if yt.get("api_key_configured") else "Using yt-dlp fallback"
        )
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


@router.post("/connections/{platform}/sessions", response_model=ConnectSessionRead)
async def start_connect_session(
    platform: str,
    body: ConnectSessionStart | None = None,
    session: AsyncSession = Depends(get_session),
) -> ConnectSessionRead:
    """Open a headed browser via the Connect Agent for platform login."""
    platform = platform.lower()
    if platform in {"youtube", "mock", "web"}:
        raise HTTPException(status_code=400, detail="This platform does not use Connect sessions")
    workspace_id = (body.workspace_id if body else "default") or "default"
    if not await agent_health():
        raise HTTPException(
            status_code=503,
            detail=(
                "Connect agent is offline. Locally run `docker compose up -d connect-agent`. "
                "On Render, deploy rivalradar-connect and set CONNECT_AGENT_URL + "
                "CONNECT_VIEWER_URL on rivalradar-api to that service's public URL."
            ),
        )

    seed_cookies: list[dict[str, object]] = []
    seed_state: dict[str, object] | None = None
    existing = await session.scalar(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == workspace_id,
            PlatformConnection.platform == platform,
        )
    )
    if existing is not None and existing.status == "connected":
        try:
            secret = decrypt_json(existing.encrypted_blob)
            raw_cookies = secret.get("cookies")
            if isinstance(raw_cookies, list):
                seed_cookies = [c for c in raw_cookies if isinstance(c, dict)]
            raw_state = secret.get("storage_state")
            if isinstance(raw_state, dict):
                seed_state = raw_state
        except Exception:  # noqa: BLE001
            seed_cookies = []
            seed_state = None

    has_saved = bool(seed_cookies or seed_state)
    open_url = connect_open_url(platform, has_saved_session=has_saved)
    session_id = str(uuid.uuid4())
    try:
        agent = await agent_start_session(
            session_id=session_id,
            platform=platform,
            login_url=open_url,
            cookies=seed_cookies or None,
            storage_state=seed_state,
        )
    except ConnectAgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    viewer = None
    raw_viewer = agent.get("viewer_url")
    if isinstance(raw_viewer, str) and raw_viewer.strip():
        viewer = raw_viewer.strip()
    configured = public_viewer_url()
    # Prefer gateway CONNECT_VIEWER_URL when the agent still returns localhost
    # (old image ENV default) so Render/Vercel operators open the public noVNC.
    if configured and (
        not viewer or "localhost" in viewer.lower() or "127.0.0.1" in viewer.lower()
    ):
        viewer = configured
    detail = str(
        agent.get("detail")
        or (
            f"Reusing saved {platform} session — confirm you're signed in, then click I've logged in."
            if has_saved
            else f"Sign in to {platform} in the Connect browser, then click I've logged in."
        )
    )
    put_session(
        ConnectSession(
            session_id=session_id,
            workspace_id=workspace_id,
            platform=platform,
            login_url=open_url,
            status="awaiting_login",
            detail=detail,
        )
    )
    return ConnectSessionRead(
        session_id=session_id,
        platform=platform,
        status="awaiting_login",
        login_url=open_url,
        detail=detail,
        agent_online=True,
        viewer_url=viewer,
    )


@router.get("/connections/{platform}/sessions/{session_id}", response_model=ConnectSessionRead)
async def read_connect_session(platform: str, session_id: str) -> ConnectSessionRead:
    platform = platform.lower()
    live = get_connect_session(session_id)
    if live is None or live.platform != platform:
        raise HTTPException(status_code=404, detail="Connect session not found")
    return ConnectSessionRead(
        session_id=live.session_id,
        platform=live.platform,
        status=live.status,  # type: ignore[arg-type]
        login_url=live.login_url,
        detail=live.detail,
        agent_online=await agent_health(),
        viewer_url=public_viewer_url(),
    )


@router.post(
    "/connections/{platform}/sessions/{session_id}/complete",
    response_model=ConnectionStatusRead,
)
async def complete_connect_session(
    platform: str,
    session_id: str,
    session: AsyncSession = Depends(get_session),
) -> ConnectionStatusRead:
    """Capture cookies from the open browser and vault them — never passwords."""
    platform = platform.lower()
    live = get_connect_session(session_id)
    if live is None or live.platform != platform:
        raise HTTPException(status_code=404, detail="Connect session not found")
    if live.status == "expired":
        await agent_close_session(session_id)
        pop_session(session_id)
        raise HTTPException(status_code=409, detail="Connect session expired — start again")
    try:
        dump = await agent_dump_session(session_id)
    except ConnectAgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    cookies_raw = dump.get("cookies")
    cookies = (
        [c for c in cookies_raw if isinstance(c, dict)] if isinstance(cookies_raw, list) else []
    )
    if not cookies:
        raise HTTPException(
            status_code=409,
            detail="No session cookies yet — finish signing in in the browser, then try again",
        )
    storage_state = dump.get("storage_state")
    secret: dict[str, object] = {"cookies": cookies, "source": "connect_session"}
    if isinstance(storage_state, dict):
        secret["storage_state"] = storage_state
    blob = encrypt_json(secret)
    expires_at = expires_at_from_cookies(cookies)
    existing = await session.scalar(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == live.workspace_id,
            PlatformConnection.platform == platform,
        )
    )
    if existing is None:
        existing = PlatformConnection(
            workspace_id=live.workspace_id,
            platform=platform,
            auth_type="cookie",
            encrypted_blob=blob,
            scopes=["read", "scout"],
            status="connected",
            expires_at=expires_at,
        )
        session.add(existing)
    else:
        existing.auth_type = "cookie"
        existing.encrypted_blob = blob
        existing.scopes = ["read", "scout"]
        existing.status = "connected"
        existing.expires_at = expires_at
    await session.commit()
    await session.refresh(existing)
    await agent_close_session(session_id)
    pop_session(session_id)
    return ConnectionStatusRead(
        platform=existing.platform,
        status="connected",
        auth_type=existing.auth_type,
        expires_at=existing.expires_at,
        scopes=list(existing.scopes or []),
        detail="Connected via browser Connect session — profile kept for soft reconnect",
    )


@router.post("/connections/{platform}/sessions/{session_id}/cancel", status_code=204)
async def cancel_connect_session(platform: str, session_id: str) -> None:
    platform = platform.lower()
    live = get_connect_session(session_id)
    if live is not None and live.platform == platform:
        pop_session(session_id)
    await agent_close_session(session_id)


@router.post("/connect/pairing", response_model=PairingCodeRead)
async def create_pairing_code(body: PairingCodeRequest | None = None) -> PairingCodeRead:
    """Issue a one-time code the Chrome extension uses to vault cookies."""
    workspace_id = (body.workspace_id if body else "default") or "default"
    try:
        code, expires_in = issue_pairing_code(workspace_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return PairingCodeRead(code=code, expires_in=expires_in, workspace_id=workspace_id)


@router.post("/connections/{platform}/quick", response_model=ConnectionStatusRead)
async def quick_connect(
    platform: str,
    body: QuickConnectRequest,
    session: AsyncSession = Depends(get_session),
) -> ConnectionStatusRead:
    """Vault platform cookies from the RivalRadar Chrome extension (no noVNC)."""
    platform = platform.lower()
    if platform not in PLATFORM_COOKIE_SPEC:
        raise HTTPException(
            status_code=400,
            detail=f"Quick connect unsupported for {platform}. Use Browser login or pick LinkedIn/X/Instagram/TikTok/Threads.",
        )
    if not consume_pairing_code(body.code, body.workspace_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired pairing code. Open Connect in RivalRadar and copy a fresh code.",
        )
    try:
        cookies = normalize_cookies(platform, body.cookies)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ok, probe_detail = await probe_session(platform, cookies)
    if not ok:
        raise HTTPException(status_code=401, detail=probe_detail)

    secret: dict[str, object] = {
        "cookies": cookies,
        "source": "chrome_extension",
    }
    blob = encrypt_json(secret)
    expires_at = expires_at_from_cookies(cookies)
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
            auth_type="cookie",
            encrypted_blob=blob,
            expires_at=expires_at,
            scopes=["read"],
            status="connected",
        )
        session.add(existing)
    else:
        existing.auth_type = "cookie"
        existing.encrypted_blob = blob
        existing.expires_at = expires_at
        existing.scopes = ["read"]
        existing.status = "connected"
    await session.commit()
    await session.refresh(existing)
    return ConnectionStatusRead(
        platform=existing.platform,
        status="connected",
        auth_type=existing.auth_type,
        expires_at=existing.expires_at,
        scopes=list(existing.scopes or []),
        detail=probe_detail,
    )


@router.post("/connections/{platform}", response_model=ConnectionStatusRead)
async def upsert_connection(
    platform: str,
    body: ConnectionUpsert,
    session: AsyncSession = Depends(get_session),
) -> ConnectionStatusRead:
    """Store encrypted OAuth token / cookie vault material — never passwords."""
    platform = platform.lower()
    if "password" in {str(k).lower() for k in body.secret}:
        raise HTTPException(
            status_code=400,
            detail="Passwords are not accepted — use OAuth or Connect session cookies",
        )
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
