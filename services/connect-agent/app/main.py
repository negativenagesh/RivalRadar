"""RivalRadar Connect Agent — opens a real browser for platform login.

Default path: Docker Compose service with Xvfb + noVNC (starts with the backend).
Optional host path for a native Mac window:

  cd services/connect-agent
  uv sync && uv run playwright install chromium
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.browser import manager

app = FastAPI(title="RivalRadar Connect Agent", version="0.2.0")


class StartBody(BaseModel):
    session_id: str
    platform: str
    login_url: str


class SessionStatus(BaseModel):
    session_id: str
    platform: str
    status: str
    login_url: str
    detail: str | None = None
    viewer_url: str | None = None


class CookiesBody(BaseModel):
    cookies: list[dict[str, Any]] = Field(default_factory=list)


def _viewer_url() -> str | None:
    value = (os.environ.get("PUBLIC_VIEWER_URL") or "").strip()
    return value or None


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
        live = await manager.start(body.session_id, body.platform, body.login_url)
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
        cookies = await manager.dump_cookies(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CookiesBody(cookies=cookies)


@app.post("/sessions/{session_id}/close", status_code=204)
async def close_session(session_id: str) -> None:
    await manager.close(session_id)
