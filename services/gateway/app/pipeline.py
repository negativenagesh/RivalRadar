from typing import Any

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients import check_compliance, generate_draft_content
from app.models import Draft

_AGENT_ID = "generation.pipeline"
_SERVICE = "gateway"


async def generate_drafts_from_digest(
    session: AsyncSession,
    digest: dict[str, Any],
    *,
    run_id: str | None = None,
    event_bus: AgentEventBus | None = None,
) -> list[Draft]:
    """For each cluster in a digest, generate a draft and run it through
    compliance, persisting every result regardless of pass/fail so a human
    reviewer can see -- and potentially override -- a compliance rejection.

    When run_id/event_bus are provided, each step is published onto the
    shared agent-events bus so a frontend can watch the pipeline agent
    work through clusters live, same mechanism ingestion's browser agent
    uses.
    """
    drafts: list[Draft] = []
    sequence = 0

    async def emit(step_type: StepType, payload: dict[str, object]) -> None:
        nonlocal sequence
        if event_bus is None or run_id is None:
            return
        sequence += 1
        await event_bus.publish(
            AgentEvent(
                run_id=run_id,
                agent_id=_AGENT_ID,
                service=_SERVICE,
                step_type=step_type,
                payload=payload,
                sequence=sequence,
            )
        )

    for cluster in digest["clusters"]:
        await emit(
            "action",
            {"stage": "generate_draft", "format": cluster["format"], "theme": cluster["dominant_theme"]},
        )
        generated = await generate_draft_content(
            cluster_format=cluster["format"],
            cluster_theme=cluster["dominant_theme"],
            competitor_caption=cluster["top_post_caption"],
        )

        await emit("action", {"stage": "compliance_check", "format": cluster["format"]})
        compliance = await check_compliance(generated["caption"])

        draft = Draft(
            digest_id=digest["id"],
            cluster_format=cluster["format"],
            cluster_theme=cluster["dominant_theme"],
            caption=generated["caption"],
            image_concept=generated["image_concept"],
            image_mime_type=generated.get("image_mime_type"),
            image_data_base64=generated.get("image_data_base64"),
            voice_examples_used=generated["voice_examples_used"],
            compliance_passed=compliance["passed"],
            compliance_rule_violations=compliance["rule_violations"],
            compliance_llm_reason=compliance["llm_reason"],
        )
        session.add(draft)
        drafts.append(draft)
        await emit(
            "log",
            {"stage": "draft_created", "compliance_passed": compliance["passed"]},
        )

    await session.commit()
    for draft in drafts:
        await session.refresh(draft)
    return drafts
