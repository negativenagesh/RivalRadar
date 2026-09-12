from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from redis.asyncio import Redis

from agent_events.schema import AgentEvent

_STREAM_MAXLEN = 500
_RUN_TTL_SECONDS = 3600


def _stream_key(run_id: str) -> str:
    return f"agent_events:{run_id}"


class AgentEventBus:
    """Publishes/replays AgentEvents for a run via one Redis Stream per run_id.

    A stream (not plain Pub/Sub) is used so a client that connects after a
    run has started still sees everything emitted so far, then keeps
    tailing live via blocking XREAD -- one primitive covers both replay and
    real-time delivery.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def publish(self, event: AgentEvent) -> None:
        key = _stream_key(event.run_id)
        await self._redis.xadd(
            key,
            {"data": event.model_dump_json()},
            maxlen=_STREAM_MAXLEN,
            approximate=True,
        )
        await self._redis.expire(key, _RUN_TTL_SECONDS)

    async def close_run(self, run_id: str, *, status: str = "done", detail: str = "") -> None:
        await self.publish(
            AgentEvent(
                run_id=run_id,
                agent_id="system",
                service="system",
                step_type="status",
                payload={"status": status, "detail": detail},
            )
        )

    async def subscribe(self, run_id: str) -> AsyncIterator[AgentEvent]:
        """Yield the run's full backlog, then tail new events until a
        terminal `status` event (done/error) is observed."""
        key = _stream_key(run_id)
        last_id = "0-0"
        while True:
            raw_entries = await self._redis.xread({key: last_id}, block=5000, count=50)
            entries = cast(
                "list[tuple[str, list[tuple[str, dict[str, str]]]]]", raw_entries
            )
            if not entries:
                continue
            for _stream_name, messages in entries:
                for message_id, fields in messages:
                    last_id = message_id
                    event = AgentEvent.model_validate_json(fields["data"])
                    yield event
                    if event.step_type == "status" and event.payload.get("status") in (
                        "done",
                        "error",
                        "cancelled",
                    ):
                        return
