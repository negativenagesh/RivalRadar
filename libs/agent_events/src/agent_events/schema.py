from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StepType = Literal["nav", "action", "screenshot", "dom_snapshot", "log", "status", "error", "artifact"]


class AgentEvent(BaseModel):
    """One step of progress emitted by any agent, for any run.

    Every browsing step, cluster/digest step, or generation step across
    ingestion/intelligence/generation/compliance publishes this same shape
    onto the shared bus, so one frontend live-view can render the whole
    pipeline regardless of which service is currently acting.
    """

    run_id: str
    agent_id: str
    service: str
    step_type: StepType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sequence: int = 0
