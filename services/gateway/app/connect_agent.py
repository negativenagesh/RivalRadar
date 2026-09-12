"""HTTP client for the Connect Agent (Playwright + optional noVNC viewer)."""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings

_OFFLINE_HINT = (
    "Connect agent is offline. Start the stack with `docker compose up -d` "
    "(includes connect-agent). Viewer: http://localhost:7900"
)


class ConnectAgentError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 503) -> None:
        super().__init__(message)
        self.status_code = status_code


def _detail_from_response(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001
        return response.text or f"agent HTTP {response.status_code}"
    detail = payload.get("detail") if isinstance(payload, dict) else None
    if isinstance(detail, str):
        return detail
    return response.text or f"agent HTTP {response.status_code}"


def public_viewer_url() -> str | None:
    value = (settings.connect_viewer_url or "").strip()
    return value or None


async def agent_health() -> bool:
    try:
        async with httpx.AsyncClient(base_url=settings.connect_agent_url, timeout=3.0) as client:
            response = await client.get("/health")
            return response.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def agent_start_session(*, session_id: str, platform: str, login_url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(base_url=settings.connect_agent_url, timeout=90.0) as client:
            response = await client.post(
                "/sessions",
                json={"session_id": session_id, "platform": platform, "login_url": login_url},
            )
    except httpx.HTTPError as exc:
        raise ConnectAgentError(_OFFLINE_HINT) from exc
    if response.status_code >= 400:
        raise ConnectAgentError(_detail_from_response(response), status_code=502)
    result: dict[str, Any] = response.json()
    return result


async def agent_dump_cookies(session_id: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(base_url=settings.connect_agent_url, timeout=30.0) as client:
            response = await client.post(f"/sessions/{session_id}/cookies")
    except httpx.HTTPError as exc:
        raise ConnectAgentError("Connect agent unreachable while reading session") from exc
    if response.status_code >= 400:
        raise ConnectAgentError(
            _detail_from_response(response),
            status_code=409 if response.status_code == 409 else 502,
        )
    data = response.json()
    cookies = data.get("cookies")
    if not isinstance(cookies, list):
        raise ConnectAgentError("Connect agent returned invalid cookies")
    return [c for c in cookies if isinstance(c, dict)]


async def agent_close_session(session_id: str) -> None:
    try:
        async with httpx.AsyncClient(base_url=settings.connect_agent_url, timeout=15.0) as client:
            await client.post(f"/sessions/{session_id}/close")
    except httpx.HTTPError:
        return
