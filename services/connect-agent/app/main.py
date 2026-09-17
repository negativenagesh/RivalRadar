"""RivalRadar Connect Agent — opens a real browser for platform login.

Default: Docker Compose with persistent Chromium profiles + noVNC.
Profiles keep you signed in across reconnects.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.browser import manager

app = FastAPI(title="RivalRadar Connect Agent", version="0.4.0")


class StartBody(BaseModel):
    session_id: str
    platform: str
    login_url: str
    cookies: list[dict[str, Any]] = Field(default_factory=list)
    storage_state: dict[str, Any] | None = None


class SessionStatus(BaseModel):
    session_id: str
    platform: str
    status: str
    login_url: str
    detail: str | None = None
    viewer_url: str | None = None


class CookiesBody(BaseModel):
    cookies: list[dict[str, Any]] = Field(default_factory=list)
    storage_state: dict[str, Any] | None = None


def _viewer_url() -> str | None:
    """Browser-facing noVNC URL.

    Prefer an explicit PUBLIC_VIEWER_URL, but ignore localhost defaults when
    running on Render (RENDER_EXTERNAL_URL) so operators don't get
    localhost:7900 from the Docker image ENV.
    """
    value = (os.environ.get("PUBLIC_VIEWER_URL") or "").strip()
    external = (os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")
    if value and not _is_local_viewer(value):
        return value
    if external:
        return f"{external}/vnc.html?autoconnect=1&resize=scale"
    return value or None


def _is_local_viewer(url: str) -> bool:
    lower = url.lower()
    return "localhost" in lower or "127.0.0.1" in lower


@app.get("/health")
async def health() -> dict[str, str | None]:
    return {
        "status": "ok",
        "service": "connect-agent",
        "viewer_url": _viewer_url(),
    }


@app.post("/sessions", response_model=SessionStatus)
async def start_session(body: StartBody) -> SessionStatus:
    try:
        live = await manager.start(
            body.session_id,
            body.platform,
            body.login_url,
            cookies=body.cookies or None,
            storage_state=body.storage_state,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to open browser: {exc}") from exc
    return SessionStatus(
        session_id=live.session_id,
        platform=live.platform,
        status=live.status,
        login_url=live.login_url,
        detail=live.detail,
        viewer_url=_viewer_url(),
    )


@app.get("/sessions/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str) -> SessionStatus:
    live = await manager.get(session_id)
    if live is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionStatus(
        session_id=live.session_id,
        platform=live.platform,
        status=live.status,
        login_url=live.login_url,
        detail=live.detail,
        viewer_url=_viewer_url(),
    )


@app.post("/sessions/{session_id}/cookies", response_model=CookiesBody)
async def dump_cookies(session_id: str) -> CookiesBody:
    try:
        payload = await manager.dump_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    cookies = payload.get("cookies")
    storage_state = payload.get("storage_state")
    return CookiesBody(
        cookies=[c for c in cookies if isinstance(c, dict)] if isinstance(cookies, list) else [],
        storage_state=storage_state if isinstance(storage_state, dict) else None,
    )


@app.post("/sessions/{session_id}/close", status_code=204)
async def close_session(session_id: str) -> None:
    await manager.close(session_id)
