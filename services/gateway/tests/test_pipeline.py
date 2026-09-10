from unittest.mock import AsyncMock

import pytest
from agent_events import AgentEventBus
from app.pipeline import generate_drafts_from_digest
from fakeredis.aioredis import FakeRedis
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures import make_compliance_response, make_digest, make_generation_response


async def test_generates_one_draft_per_cluster(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = make_digest(
        clusters=[
            {
                "format": "meme",
                "dominant_theme": "monday-mood",
                "top_post_caption": "mondays am I right",
                "post_count": 1,
                "total_engagement": 100,
                "avg_engagement": 100.0,
                "top_post_id": "p1",
                "account_ids": ["acc-1"],
            },
            {
                "format": "founder_post",
                "dominant_theme": "sustainability",
                "top_post_caption": "we planted trees",
                "post_count": 1,
                "total_engagement": 200,
                "avg_engagement": 200.0,
                "top_post_id": "p2",
                "account_ids": ["acc-1"],
            },
        ]
    )
    monkeypatch.setattr(
        "app.pipeline.generate_draft_content", AsyncMock(return_value=make_generation_response())
    )
    monkeypatch.setattr(
        "app.pipeline.check_compliance", AsyncMock(return_value=make_compliance_response())
    )

    drafts = await generate_drafts_from_digest(session, digest)

    assert len(drafts) == 2
    assert {d.cluster_format for d in drafts} == {"meme", "founder_post"}


async def test_persists_compliance_failure_rather_than_dropping_draft(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = make_digest()
    monkeypatch.setattr(
        "app.pipeline.generate_draft_content", AsyncMock(return_value=make_generation_response())
    )
    monkeypatch.setattr(
        "app.pipeline.check_compliance",
        AsyncMock(return_value=make_compliance_response(passed=False)),
    )

    drafts = await generate_drafts_from_digest(session, digest)

    assert len(drafts) == 1
    assert drafts[0].compliance_passed is False
    assert drafts[0].compliance_llm_reason == "flagged for testing"


async def test_emits_agent_events_when_bus_provided(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    digest = make_digest()
    monkeypatch.setattr(
        "app.pipeline.generate_draft_content", AsyncMock(return_value=make_generation_response())
    )
    monkeypatch.setattr(
        "app.pipeline.check_compliance", AsyncMock(return_value=make_compliance_response())
    )
    bus = AgentEventBus(FakeRedis(decode_responses=True))

    await generate_drafts_from_digest(session, digest, run_id="run-1", event_bus=bus)
    await bus.close_run("run-1")

    events = [event async for event in bus.subscribe("run-1")]
    step_types = [e.step_type for e in events]
    assert "action" in step_types
    assert "log" in step_types
    assert step_types[-1] == "status"
