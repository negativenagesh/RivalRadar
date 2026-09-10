from functools import lru_cache

from agent_events import AgentEventBus
from agent_events.factory import build_agent_event_bus

from app.config import settings


@lru_cache(maxsize=1)
def get_event_bus() -> AgentEventBus:
    return build_agent_event_bus(settings.redis_url)
