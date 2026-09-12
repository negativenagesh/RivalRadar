import pytest
from agent_events.bus import AgentEventBus
from agent_events.schema import AgentEvent
from fakeredis.aioredis import FakeRedis


@pytest.fixture
def bus() -> AgentEventBus:
    return AgentEventBus(FakeRedis(decode_responses=True))


async def test_subscribe_replays_backlog_then_stops_on_done(bus: AgentEventBus) -> None:
    run_id = "run-1"
    await bus.publish(
        AgentEvent(run_id=run_id, agent_id="a", service="ingestion", step_type="nav")
    )
    await bus.publish(
        AgentEvent(run_id=run_id, agent_id="a", service="ingestion", step_type="action")
    )
    await bus.close_run(run_id)

    events = [event async for event in bus.subscribe(run_id)]

    assert [e.step_type for e in events] == ["nav", "action", "status"]
    assert events[-1].payload["status"] == "done"


async def test_subscribe_stops_on_error_status(bus: AgentEventBus) -> None:
    run_id = "run-2"
    await bus.close_run(run_id, status="error", detail="boom")

    events = [event async for event in bus.subscribe(run_id)]

    assert events[-1].payload == {"status": "error", "detail": "boom"}


async def test_subscribe_stops_on_cancelled_status(bus: AgentEventBus) -> None:
    run_id = "run-3"
    await bus.close_run(run_id, status="cancelled", detail="cancelled by operator")

    events = [event async for event in bus.subscribe(run_id)]

    assert events[-1].payload == {"status": "cancelled", "detail": "cancelled by operator"}
