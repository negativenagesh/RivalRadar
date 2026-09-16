import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_and_upsert_connection(client: AsyncClient) -> None:
    listed = await client.get("/connections")
    assert listed.status_code == 200
    rows = listed.json()
    assert any(r["platform"] == "youtube" for r in rows)

    created = await client.post(
        "/connections/tiktok",
        json={
            "auth_type": "cookie",
            "secret": {"session": "opaque-cookie-bundle"},
            "scopes": ["read"],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["platform"] == "tiktok"
    assert body["status"] == "connected"

    # Passwords rejected
    bad = await client.post(
        "/connections/linkedin",
        json={"auth_type": "oauth", "secret": {"password": "nope"}},
    )
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_connect_session_flow(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _health() -> bool:
        return True

    async def _start(
        *,
        session_id: str,
        platform: str,
        login_url: str,
        cookies: list[dict[str, object]] | None = None,
        storage_state: dict[str, object] | None = None,
    ) -> dict[str, str]:
        assert platform == "instagram"
        assert "instagram" in login_url
        _ = cookies, storage_state
        return {"session_id": session_id, "status": "awaiting_login", "detail": "ok"}

    async def _dump(session_id: str) -> dict[str, object]:
        _ = session_id
        return {
            "cookies": [
                {
                    "name": "sessionid",
                    "value": "abc",
                    "domain": ".instagram.com",
                    "path": "/",
                    "expires": 2_000_000_000,
                }
            ],
            "storage_state": {"cookies": [], "origins": []},
        }

    async def _close(session_id: str) -> None:
        return None

    monkeypatch.setattr("app.routes.agent_health", _health)
    monkeypatch.setattr("app.routes.agent_start_session", _start)
    monkeypatch.setattr("app.routes.agent_dump_session", _dump)
    monkeypatch.setattr("app.routes.agent_close_session", _close)

    started = await client.post("/connections/instagram/sessions", json={"workspace_id": "default"})
    assert started.status_code == 200
    session = started.json()
    assert session["status"] == "awaiting_login"
    assert session["session_id"]

    done = await client.post(
        f"/connections/instagram/sessions/{session['session_id']}/complete"
    )
    assert done.status_code == 200
    assert done.json()["status"] == "connected"
    assert done.json()["auth_type"] == "cookie"
    assert done.json()["expires_at"] is not None


@pytest.mark.asyncio
async def test_connect_session_agent_offline(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _health() -> bool:
        return False

    monkeypatch.setattr("app.routes.agent_health", _health)
    response = await client.post("/connections/linkedin/sessions", json={})
    assert response.status_code == 503
    detail = response.json()["detail"].lower()
    assert "connect agent is offline" in detail
    assert "docker compose" in detail or "rivalradar-connect" in detail
