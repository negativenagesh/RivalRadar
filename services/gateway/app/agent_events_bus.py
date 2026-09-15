from functools import lru_cache

from agent_events import AgentEventBus
from agent_events.factory import build_agent_event_bus

from app.config import settings


@lru_cache(maxsize=1)
def get_event_bus() -> AgentEventBus:
    """Redis Streams bus; falls back to in-process FakeRedis when REDIS_URL=memory."""
    if settings.use_memory_redis:
        from fakeredis.aioredis import FakeRedis

        return AgentEventBus(FakeRedis(decode_responses=True))
    return build_agent_event_bus(settings.redis_url)
