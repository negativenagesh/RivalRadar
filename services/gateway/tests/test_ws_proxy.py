from __future__ import annotations

import asyncio
from typing import Any

import pytest
from app.ws_proxy import http_base_to_ws, ingestion_live_upstream_url, proxy_client_to_upstream
from starlette.websockets import WebSocketState


def test_http_base_to_ws() -> None:
    assert http_base_to_ws("http://127.0.0.1:8001") == "ws://127.0.0.1:8001"
    assert http_base_to_ws("https://api.example.com/") == "wss://api.example.com"
    assert http_base_to_ws("ws://127.0.0.1:8001") == "ws://127.0.0.1:8001"
    assert http_base_to_ws("127.0.0.1:8001") == "ws://127.0.0.1:8001"


def test_ingestion_live_upstream_url() -> None:
    assert (
        ingestion_live_upstream_url("http://127.0.0.1:8001", "run-1")
        == "ws://127.0.0.1:8001/ingest/runs/run-1/live"
    )


class _FakeClient:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.client_state = WebSocketState.CONNECTED
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    async def receive(self) -> dict[str, Any]:
        return await self._queue.get()

    def disconnect(self) -> None:
        self._queue.put_nowait({"type": "websocket.disconnect"})


class _FakeUpstream:
    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.closed = False

    async def recv(self) -> str:
        if not self._messages:
            from websockets.exceptions import ConnectionClosed

            raise ConnectionClosed(None, None)
        return self._messages.pop(0)

    async def close(self) -> None:
        self.closed = True

    async def __aenter__(self) -> _FakeUpstream:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()


@pytest.mark.asyncio
async def test_proxy_forwards_upstream_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = _FakeUpstream(
        [
            '{"step_type":"nav","payload":{"url":"https://example.com"}}',
            '{"step_type":"status","payload":{"status":"done"}}',
        ]
    )

    def _connect(url: str, **kwargs: object) -> _FakeUpstream:
        assert "ingest/runs/abc/live" in url
        return upstream

    monkeypatch.setattr("app.ws_proxy.websockets.connect", _connect)
    client = _FakeClient()

    task = asyncio.create_task(
        proxy_client_to_upstream(client, "ws://127.0.0.1:8001/ingest/runs/abc/live")
    )
    for _ in range(50):
        if len(client.sent) >= 2:
            break
        await asyncio.sleep(0.05)
    client.disconnect()
    await asyncio.wait_for(task, timeout=2.0)

    assert len(client.sent) == 2
    assert "nav" in client.sent[0]
    assert "done" in client.sent[1]


@pytest.mark.asyncio
async def test_proxy_connect_failure_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def _connect(url: str, **kwargs: object) -> Any:
        raise ConnectionRefusedError("ingestion down")

    monkeypatch.setattr("app.ws_proxy.websockets.connect", _connect)
    client = _FakeClient()
    with pytest.raises(ConnectionRefusedError):
        await proxy_client_to_upstream(client, "ws://127.0.0.1:9/ingest/runs/x/live")
