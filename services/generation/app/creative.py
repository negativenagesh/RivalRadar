from __future__ import annotations

import base64
import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.parse import parse_json_object, voice_guard
from app.agents.prompts import (
    COMMENT_SNIPER,
    FORMAT_DIRECTOR,
    FORMAT_SPECS,
    IMAGE_NEGATIVES,
    MEME_LORD,
)
from llm_provider import LLMProvider, Message

logger = logging.getLogger(__name__)

CreativeKind = Literal["image", "comment", "reply", "studio"]

_CHAR_CAP = {"linkedin": 280, "x": 220, "twitter": 220, "instagram": 180}


class CreativeRequest(BaseModel):
    kind: CreativeKind
    report_markdown: str = ""
    brand_name: str = "the brand"
    voice_notes: str = ""
    competitor_caption: str = ""
    forbidden_claims: str = ""
    platform: str | None = None
    format: str | None = None
    spice: int = 3
    tone: str | None = None
    post_url: str | None = None
    facts_json: str | None = None


class CreativeResponse(BaseModel):
    kind: CreativeKind
    text: str
    image_concept: str | None = None
    image_mime_type: str | None = None
    image_data_base64: str | None = None
    why_slaps: str | None = None
    overlay_text: str | None = None
    hashtags: list[str] = Field(default_factory=list)


def _spice_label(spice: int) -> str:
    n = max(1, min(5, spice))
    return {1: "wholesome hype", 2: "witty", 3: "witty", 4: "petty", 5: "unhinged-but-safe"}[n]


async def _maybe_image(provider: LLMProvider, brief: str, brand: str) -> tuple[str | None, str | None]:
    try:
        image = await provider.generate_image(
            brief,
            style_hints=[brand, "electric lime accents", "dark editorial", IMAGE_NEGATIVES],
        )
        return image.mime_type, base64.b64encode(image.data).decode("ascii")
    except Exception:  # noqa: BLE001
        logger.warning("creative generate_image failed; concept-only", exc_info=True)
        return None, None


async def generate_creative(request: CreativeRequest, provider: LLMProvider) -> CreativeResponse:
    report_excerpt = (request.report_markdown or "")[:3500]
    voice = request.voice_notes or "on-brand, sharp, human"
    facts = (request.facts_json or "")[:4000]
    platform = (request.platform or "linkedin").lower()
    if platform == "twitter":
        platform = "x"

    if request.kind == "comment":
        cap = _CHAR_CAP.get(platform, 220)
        messages: list[Message] = [
            Message(role="system", content=COMMENT_SNIPER),
            Message(
                role="user",
                content=(
                    f"Brand: {request.brand_name}\nVoice: {voice}\n"
                    f"Platform: {platform}\nTone: {request.tone or _spice_label(request.spice)}\n"
                    f"Spice: {request.spice}/5\nMax chars: {cap}\n"
                    f"Rival permalink: {request.post_url or '(none)'}\n"
                    f"Rival post: {request.competitor_caption or '(from discovery themes)'}\n"
                    f"Forbidden: {request.forbidden_claims or 'none'}\n"
                    f"Facts:\n{facts or report_excerpt}\n"
                ),
            ),
        ]
        text = (await provider.complete(messages, temperature=0.8, max_tokens=160)).strip().strip('"')
        text = await voice_guard(text, forbidden=request.forbidden_claims, provider=provider)
        return CreativeResponse(kind="comment", text=text[:cap])

    if request.kind == "reply":
        messages = [
            Message(
                role="system",
                content=(
                    "You draft a response/reply post caption in the brand voice. "
                    "Punchy, specific, not mean-spirited. Max 280 characters."
                ),
            ),
            Message(
                role="user",
                content=(
                    f"Brand: {request.brand_name}\nVoice: {voice}\n"
                    f"Discovery report:\n{report_excerpt}\n\n"
                    "Draft one reply/response caption the brand could publish after human approval."
                ),
            ),
        ]
        text = (await provider.complete(messages, temperature=0.8, max_tokens=160)).strip().strip('"')
        text = await voice_guard(text, forbidden=request.forbidden_claims, provider=provider)
        return CreativeResponse(kind="reply", text=text)

    if request.kind == "studio":
        fmt = request.format or "hot_take"
        spec = FORMAT_SPECS.get(fmt, FORMAT_SPECS["hot_take"])
        director = MEME_LORD if fmt == "meme" else FORMAT_DIRECTOR
        crop = {"instagram": "4:5", "linkedin": "1:1", "x": "1:1", "youtube": "16:9"}.get(
            platform, "1:1"
        )
        user = (
            f"Brand: {request.brand_name}\nVoice: {voice}\nPlatform: {platform} crop {crop}\n"
            f"Format: {fmt}\nSpec: {spec}\nSpice: {request.spice}/5 ({_spice_label(request.spice)})\n"
            f"Forbidden: {request.forbidden_claims or 'none'}\n"
            f"Facts:\n{facts or report_excerpt}\n"
        )
        raw = await provider.complete(
            [Message(role="system", content=director), Message(role="user", content=user)],
            temperature=0.85 if fmt != "meme" else 0.95,
            max_tokens=700,
        )
        try:
            data = parse_json_object(raw)
        except Exception:  # noqa: BLE001
            data = {"caption": raw.strip(), "image_brief": raw.strip(), "why_slaps": "", "overlay_text": "", "hashtags": []}
        caption = await voice_guard(
            str(data.get("caption") or "").strip(),
            forbidden=request.forbidden_claims,
            provider=provider,
        )
        image_brief = str(data.get("image_brief") or caption)
        brief = (
            f"{image_brief}\nAspect {crop}. Single frame. Overlay: "
            f"{data.get('overlay_text') or 'none'}. {IMAGE_NEGATIVES}"
        )
        concept = await provider.generate_image_concept(
            brief,
            style_hints=[request.brand_name, "electric lime accents", "dark editorial"],
        )
        mime, b64 = await _maybe_image(provider, brief, request.brand_name)
        raw_tags = data.get("hashtags")
        tags = [str(t) for t in raw_tags][:3] if isinstance(raw_tags, list) else []
        return CreativeResponse(
            kind="studio",
            text=caption or concept,
            image_concept=concept,
            image_mime_type=mime,
            image_data_base64=b64,
            why_slaps=str(data.get("why_slaps") or "") or None,
            overlay_text=str(data.get("overlay_text") or "") or None,
            hashtags=tags,
        )

    # image (legacy Nano Banana button)
    brief = (
        f"Create a social-ready visual concept for {request.brand_name}. "
        f"Voice: {voice}. Based on this discovery report:\n{report_excerpt}\n"
        "Describe a single bold frame suitable for Instagram/LinkedIn — no logos of rivals. "
        f"{IMAGE_NEGATIVES}"
    )
    concept = await provider.generate_image_concept(
        brief,
        style_hints=[request.brand_name, "electric lime accents", "dark editorial"],
    )
    mime, b64 = await _maybe_image(provider, brief, request.brand_name)
    return CreativeResponse(
        kind="image",
        text=concept.strip(),
        image_concept=concept.strip(),
        image_mime_type=mime,
        image_data_base64=b64,
    )
