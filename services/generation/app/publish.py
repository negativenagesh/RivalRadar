"""Publish Strategist — platform-native viral captions/hashtags for generated assets."""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.parse import parse_json_object
from app.agents.prompts import PUBLISH_STRATEGIST, VOICE_GUARD
from llm_provider import LLMProvider, Message

logger = logging.getLogger(__name__)

PLATFORMS = frozenset({"linkedin", "instagram", "x", "youtube"})

_CHAR_CAPS = {"linkedin": 2900, "instagram": 2100, "x": 270, "youtube": 5000}

_TAG_RE = re.compile(r"^#[a-z0-9_]{1,59}$")

_BANNED_GENERIC = frozenset(
    {
        "#marketing",
        "#growth",
        "#branding",
        "#brandstrategy",
        "#socialmedia",
        "#contentmarketing",
        "#viral",
        "#business",
        "#entrepreneur",
        "#success",
        "#motivation",
        "#digitalmarketing",
        "#ai",
        "#tech",
    }
)


class PublishVariation(BaseModel):
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    title: str = ""
    description: str = ""
    why: str = ""


class PublishPlanRequest(BaseModel):
    brand_name: str = Field(min_length=1, max_length=120)
    platform: Literal["linkedin", "instagram", "x", "youtube"]
    voice_notes: str | None = None
    forbidden_claims: str | None = None
    format: str = "hot_take"
    spice: int = Field(default=3, ge=1, le=5)
    asset_caption: str = ""
    overlay_text: str | None = None
    asset_context: str | None = None
    image_concept: str | None = None
    intel_markdown: str | None = None
    variations: int = Field(default=3, ge=1, le=3)
    facts_json: str | None = None


class PublishPlanResponse(BaseModel):
    platform: str
    agent: str = "publish_strategist"
    variations: list[PublishVariation] = Field(default_factory=list)


def _clean_hashtags(raw: Any, platform: str, limit: int) -> list[str]:
    """Normalize agent hashtags. Never invent or fill — empty in ⇒ empty out."""
    del platform
    out: list[str] = []
    seen: set[str] = set()
    for tag in raw if isinstance(raw, list) else []:
        text = str(tag).strip().lower().replace(" ", "")
        if not text:
            continue
        if not text.startswith("#"):
            text = f"#{text}"
        if not _TAG_RE.match(text) or text in seen or text in _BANNED_GENERIC:
            continue
        seen.add(text)
        out.append(text)
    return out[:limit]


def _fallback_variations(request: PublishPlanRequest) -> list[PublishVariation]:
    base = (request.asset_caption or f"{request.brand_name} drop").strip()
    cap = _CHAR_CAPS[request.platform]
    caption = base[:cap]
    return [
        PublishVariation(
            caption=caption,
            hashtags=[],
            title=f"{request.brand_name} — {request.format}"[:95]
            if request.platform == "youtube"
            else "",
            description=caption if request.platform == "youtube" else "",
            why="fallback: asset caption only (no invented hashtags)",
        )
    ]


def _parse_variations(raw: dict[str, Any], request: PublishPlanRequest) -> list[PublishVariation]:
    items = raw.get("variations")
    if not isinstance(items, list):
        return []
    cap = _CHAR_CAPS[request.platform]
    tag_limit = {"linkedin": 5, "instagram": 25, "x": 2, "youtube": 15}[request.platform]
    out: list[PublishVariation] = []
    for item in items[: request.variations]:
        if not isinstance(item, dict):
            continue
        caption = str(item.get("caption") or "").strip()[:cap]
        if not caption and request.platform != "youtube":
            continue
        out.append(
            PublishVariation(
                caption=caption,
                hashtags=_clean_hashtags(item.get("hashtags"), request.platform, tag_limit),
                title=str(item.get("title") or "")[:95] if request.platform == "youtube" else "",
                description=str(item.get("description") or "")[:cap]
                if request.platform == "youtube"
                else "",
                why=str(item.get("why") or "")[:240],
            )
        )
    return out


def _publish_user_prompt(request: PublishPlanRequest) -> str:
    facts = (request.facts_json or "")[:6000]
    intel = (request.intel_markdown or "")[:4000]
    image_concept = (request.image_concept or "")[:1500]
    asset_context = (request.asset_context or "")[:800]
    return (
        f"Brand: {request.brand_name}\n"
        f"Platform: {request.platform}\n"
        f"Format of the generated asset: {request.format} (spice {request.spice}/5)\n"
        f"Asset caption/text: {request.asset_caption or '(image only)'}\n"
        f"Asset overlay text: {request.overlay_text or 'none'}\n"
        f"Asset context (why it slaps / angle): {asset_context or 'none'}\n"
        f"Image concept / visual described: {image_concept or 'none — invent tags from caption + facts'}\n"
        f"Voice: {request.voice_notes or 'sharp, human'}\n"
        f"Forbidden: {request.forbidden_claims or 'none listed'}\n"
        f"Write exactly {request.variations} variation(s).\n"
        "Hashtags must be invented from the fields above + FACTS/intel — never generic filler.\n\n"
        f"FACTS + roast pack (angle fuel, do not quote metrics as claims):\n{facts or '(none)'}\n\n"
        f"INTEL BRIEF (optional angle fuel):\n{intel or '(none)'}"
    )


async def _guard_variations(
    request: PublishPlanRequest,
    variations: list[PublishVariation],
    provider: LLMProvider,
) -> list[PublishVariation]:
    guarded: list[PublishVariation] = []
    for variation in variations:
        text = variation.caption
        if text:
            try:
                checked = await provider.complete(
                    [
                        Message(role="system", content=VOICE_GUARD),
                        Message(
                            role="user",
                            content=f"Forbidden: {request.forbidden_claims or 'none'}\n\n{text}",
                        ),
                    ],
                    temperature=0.2,
                    max_tokens=1200,
                    reasoning_effort="low",
                )
                checked = checked.strip()
                if checked and len(checked) <= _CHAR_CAPS[request.platform]:
                    text = checked
            except Exception:  # noqa: BLE001
                pass
        guarded.append(variation.model_copy(update={"caption": text}))
    return guarded


async def generate_publish_plan(
    request: PublishPlanRequest, provider: LLMProvider
) -> PublishPlanResponse:
    user = _publish_user_prompt(request)
    try:
        raw_text = await provider.complete(
            [Message(role="system", content=PUBLISH_STRATEGIST), Message(role="user", content=user)],
            temperature=0.6 + request.spice * 0.06,
            max_tokens=2600,
            reasoning_effort="low",
        )
        data = parse_json_object(raw_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("publish strategist failed: %s", exc)
        data = {}

    variations = _parse_variations(data, request)
    if not variations:
        variations = _fallback_variations(request)
        return PublishPlanResponse(platform=request.platform, variations=variations)

    guarded = await _guard_variations(request, variations, provider)
    return PublishPlanResponse(platform=request.platform, variations=guarded)


async def generate_publish_plan_events(
    request: PublishPlanRequest, provider: LLMProvider
) -> AsyncIterator[dict[str, Any]]:
    """SSE: text deltas while the strategist writes, then the final plan."""
    yield {"event": "stage", "agent": "publish_strategist", "status": "writing"}
    user = _publish_user_prompt(request)
    buf = ""
    try:
        async for piece in provider.complete_stream(
            [Message(role="system", content=PUBLISH_STRATEGIST), Message(role="user", content=user)],
            temperature=0.6 + request.spice * 0.06,
            max_tokens=2600,
            reasoning_effort="low",
        ):
            if not piece:
                continue
            buf += piece
            yield {"event": "delta", "agent": "publish_strategist", "text": piece}
        data = parse_json_object(buf) if buf.strip() else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("publish strategist stream failed: %s", exc)
        data = {}

    variations = _parse_variations(data, request)
    if not variations:
        variations = _fallback_variations(request)
        plan = PublishPlanResponse(platform=request.platform, variations=variations)
        yield {"event": "plan", "plan": plan.model_dump(mode="json")}
        return

    guarded = await _guard_variations(request, variations, provider)
    plan = PublishPlanResponse(platform=request.platform, variations=guarded)
    yield {"event": "plan", "plan": plan.model_dump(mode="json")}


def publish_caption_text(variation: PublishVariation) -> str:
    parts = [variation.caption.strip()] if variation.caption.strip() else []
    if variation.hashtags:
        parts.append(" ".join(variation.hashtags))
    return "\n\n".join(parts)
