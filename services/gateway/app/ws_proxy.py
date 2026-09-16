"""Proxy browser WebSockets to upstream services.

Scout events are published on the *ingestion* process event bus. With
REDIS_URL=memory (Render free tier), gateway and ingestion do not share
FakeRedis — so the gateway must forward /ingestion/runs/{id}/live to
ingestion's /ingest/runs/{id}/live instead of subscribing locally.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Mapping
from typing import Any, Protocol

import websockets
from starlette.websockets import WebSocketDisconnect, WebSocketState
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class LiveClient(Protocol):
    client_state: WebSocketState

    async def send_text(self, data: str) -> Any: ...

    async def receive(self) -> Mapping[str, Any]: ...


def http_base_to_ws(url: str) -> str:
    base = url.rstrip("/")
    if base.startswith("https://"):
        return "wss://" + base.removeprefix("https://")
    if base.startswith("http://"):
        return "ws://" + base.removeprefix("http://")
    if base.startswith(("ws://", "wss://")):
        return base
    return f"ws://{base}"


def ingestion_live_upstream_url(ingestion_http_base: str, run_id: str) -> str:
    return f"{http_base_to_ws(ingestion_http_base)}/ingest/runs/{run_id}/live"


async def proxy_client_to_upstream(
    client: LiveClient,
    upstream_url: str,
    *,
    connect_timeout_s: float = 8.0,
) -> None:
    """Forward upstream text frames to an already-accepted client WebSocket."""

    async def _watch_client_disconnect(stop: asyncio.Event) -> None:
        try:
            while not stop.is_set():
                message = await client.receive()
                if message.get("type") == "websocket.disconnect":
                    break
        except WebSocketDisconnect:
            pass
        finally:
            stop.set()

    stop = asyncio.Event()
    watcher = asyncio.create_task(_watch_client_disconnect(stop))
    try:
        async with websockets.connect(
            upstream_url,
            open_timeout=connect_timeout_s,
        ) as upstream:
            while not stop.is_set():
                try:
                    raw = await asyncio.wait_for(upstream.recv(), timeout=1.0)
                except TimeoutError:
                    continue
                except ConnectionClosed:
                    break
                text = raw if isinstance(raw, str) else raw.decode("utf-8", "replace")
                if client.client_state != WebSocketState.CONNECTED:
                    break
                await client.send_text(text)
    finally:
        stop.set()
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
