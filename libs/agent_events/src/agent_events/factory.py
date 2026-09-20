from __future__ import annotations

from redis.asyncio import Redis, from_url

from agent_events.bus import AgentEventBus


def build_agent_event_bus(redis_url: str) -> AgentEventBus:
    # socket_timeout=None: blocking XREAD for live feeds must outlive the block window.
    redis: Redis = from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=None,
    )
    return AgentEventBus(redis)
