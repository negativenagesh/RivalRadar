from __future__ import annotations

import json
import re
from typing import Any

from app.agents.prompts import VOICE_GUARD
from llm_provider import LLMProvider, Message

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def parse_json_object(raw: str) -> dict[str, Any]:
    text = _FENCE.sub("", (raw or "").strip()).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON was not an object")
    return data


async def voice_guard(
    text: str,
    *,
    forbidden: str,
    provider: LLMProvider,
) -> str:
    draft = (text or "").strip()
    if not draft:
        return draft
    claims = (forbidden or "").strip()
    if not claims:
        return draft
    low = draft.lower()
    if (
        not any(part.strip() and part.strip().lower() in low for part in claims.split(","))
        and "guarantee" not in low
        and "#1" not in low
        and "number one" not in low
    ):
        return draft
    rewritten = await provider.complete(
        [
            Message(role="system", content=VOICE_GUARD),
            Message(
                role="user",
                content=f"Forbidden claims:\n{claims}\n\nDraft:\n{draft}",
            ),
        ],
        temperature=0.1,
        max_tokens=400,
        reasoning_effort="low",
    )
    return (rewritten or draft).strip().strip('"')
