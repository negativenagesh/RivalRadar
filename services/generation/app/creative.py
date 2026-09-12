from __future__ import annotations

import base64
import logging
from typing import Literal

from pydantic import BaseModel

from llm_provider import LLMProvider, Message

logger = logging.getLogger(__name__)

CreativeKind = Literal["image", "comment", "reply"]


class CreativeRequest(BaseModel):
    kind: CreativeKind
    report_markdown: str
    brand_name: str = "the brand"
    voice_notes: str = ""
    competitor_caption: str = ""


class CreativeResponse(BaseModel):
    kind: CreativeKind
    text: str
    image_concept: str | None = None
    image_mime_type: str | None = None
    image_data_base64: str | None = None


async def generate_creative(request: CreativeRequest, provider: LLMProvider) -> CreativeResponse:
    report_excerpt = request.report_markdown[:3500]
    voice = request.voice_notes or "on-brand, sharp, human"

    if request.kind == "comment":
        messages: list[Message] = [
            Message(
                role="system",
                content=(
                    "You write short social comments for human approval only. "
                    "Never claim you will auto-post. Max 220 characters. No hashtag spam."
                ),
            ),
            Message(
                role="user",
                content=(
                    f"Brand: {request.brand_name}\nVoice: {voice}\n"
                    f"Rival post: {request.competitor_caption or '(from discovery themes)'}\n"
                    f"Discovery report:\n{report_excerpt}\n\n"
                    "Write ONE comment suggestion the brand could leave (human must approve)."
                ),
            ),
        ]
        text = (await provider.complete(messages, temperature=0.7, max_tokens=120)).strip().strip('"')
        return CreativeResponse(kind="comment", text=text)

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
        return CreativeResponse(kind="reply", text=text)

    # image
    brief = (
        f"Create a social-ready visual concept for {request.brand_name}. "
        f"Voice: {voice}. Based on this discovery report:\n{report_excerpt}\n"
        "Describe a single bold frame suitable for Instagram/LinkedIn — no logos of rivals."
    )
    concept = await provider.generate_image_concept(
        brief,
        style_hints=[request.brand_name, "electric lime accents", "dark editorial"],
    )
    image_mime_type: str | None = None
    image_data_base64: str | None = None
    try:
        image = await provider.generate_image(
            brief,
            style_hints=[request.brand_name, "electric lime accents", "dark editorial"],
        )
        image_mime_type = image.mime_type
        image_data_base64 = base64.b64encode(image.data).decode("ascii")
    except Exception:
        logger.warning("creative generate_image failed; concept-only", exc_info=True)

    return CreativeResponse(
        kind="image",
        text=concept.strip(),
        image_concept=concept.strip(),
        image_mime_type=image_mime_type,
        image_data_base64=image_data_base64,
    )
