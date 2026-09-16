from functools import lru_cache

from agent_events import AgentEventBus
from fakeredis.aioredis import FakeRedis
from redis.asyncio import from_url

from app.config import settings


@lru_cache(maxsize=1)
def get_event_bus() -> AgentEventBus:
    """Redis Streams bus; falls back to in-process FakeRedis when REDIS_URL=memory.

    Note: FakeRedis is per-process. Live WS on the gateway will not see events
    unless both share a real REDIS_URL (e.g. Upstash). Status polling still works.
    """
    raw = (settings.redis_url or "").strip().lower()
    if raw in {"", "memory", "memory://", "none", "off"}:
        return AgentEventBus(FakeRedis(decode_responses=True))
    return AgentEventBus(from_url(settings.redis_url, decode_responses=True))
