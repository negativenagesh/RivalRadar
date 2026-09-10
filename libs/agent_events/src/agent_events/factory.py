from __future__ import annotations

from redis.asyncio import Redis, from_url

from agent_events.bus import AgentEventBus


def build_agent_event_bus(redis_url: str) -> AgentEventBus:
    redis: Redis = from_url(redis_url, decode_responses=True)
    return AgentEventBus(redis)
