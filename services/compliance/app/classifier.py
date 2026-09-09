import json

from pydantic import BaseModel, ValidationError

from llm_provider import LLMProvider, Message

CLASSIFIER_SYSTEM_PROMPT = (
    "You are a brand-safety reviewer for a marketing team. Given a draft social "
    "media caption, judge whether it is safe to publish. Flag anything that is: "
    "misleading, could embarrass the brand, mimics a specific competitor too "
    "closely, or takes a stance on a divisive political/religious topic. Do NOT "
    "flag ordinary marketing enthusiasm, humor, or brand voice quirks, and do "
    "not comment on spelling, capitalization, or punctuation style -- a "
    "separate automated check already handles that. "
    "Respond with ONLY raw JSON, no commentary, no markdown code fence, no "
    'explanation before or after it: {"safe": true|false, "reason": "<one '
    'sentence, empty string if safe>"}'
)


class ClassifierResult(BaseModel):
    safe: bool
    reason: str


async def run_llm_classifier(text: str, provider: LLMProvider) -> ClassifierResult:
    """LLM-judgment pass for brand-safety nuance that regex rules can't capture.

    Runs after (and independently of) the rule-based checks in rules.py --
    a draft must pass both to be considered compliant.
    """
    response = await provider.complete(
        [
            Message(role="system", content=CLASSIFIER_SYSTEM_PROMPT),
            Message(role="user", content=text),
        ],
        temperature=0.0,
        max_tokens=500,
        reasoning_effort="low",
    )

    try:
        payload = json.loads(_strip_code_fence(response))
        return ClassifierResult.model_validate(payload)
    except (json.JSONDecodeError, ValidationError):
        return ClassifierResult(
            safe=False,
            reason=f"classifier returned an unparseable response: {response[:200]!r}",
        )


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        stripped = stripped.removesuffix("```").strip()
    return stripped
