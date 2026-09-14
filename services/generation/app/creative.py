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
from llm_provider import LLMProvider, LLMProviderError, Message

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
    # Optional brand dossier (also often embedded inside facts_json roast pack).
    brand_category: str = ""
    ideal_customer: str = ""
    content_pillars: str = ""
    preferred_formats: list[str] = Field(default_factory=list)
    # 1-based index when the operator asks for a batch of memes/studio frames.
    variant: int = Field(default=1, ge=1, le=3)
    variant_count: int = Field(default=1, ge=1, le=3)


def _brand_dossier_lines(request: CreativeRequest) -> str:
    lines = [f"Brand name: {request.brand_name}", f"Voice: {request.voice_notes or 'on-brand, sharp, human'}"]
    if request.brand_category:
        lines.append(f"Category: {request.brand_category}")
    if request.ideal_customer:
        lines.append(f"ICP: {request.ideal_customer}")
    if request.content_pillars:
        lines.append(f"Content pillars: {request.content_pillars}")
    if request.preferred_formats:
        lines.append(f"Preferred formats: {', '.join(request.preferred_formats)}")
    if request.forbidden_claims:
        lines.append(f"Forbidden claims: {request.forbidden_claims}")
    return "\n".join(lines)


class CreativeResponse(BaseModel):
    kind: CreativeKind
    text: str
    image_concept: str | None = None
    image_mime_type: str | None = None
    image_data_base64: str | None = None
    image_error: str | None = None
    why_slaps: str | None = None
    overlay_text: str | None = None
    hashtags: list[str] = Field(default_factory=list)


def _spice_label(spice: int) -> str:
    n = max(1, min(5, spice))
    return {
        1: "wholesome absurdist",
        2: "witty",
        3: "petty roast",
        4: "HARD chaotic dunk",
        5: "unhinged brainrot (safe)",
    }[n]


def _meme_temperature(spice: int) -> float:
    n = max(1, min(5, spice))
    return {1: 0.95, 2: 1.0, 3: 1.1, 4: 1.2, 5: 1.25}[n]


def _looks_like_metric_overlay(overlay: str) -> bool:
    t = overlay.lower()
    if not t:
        return False
    metricish = any(
        token in t
        for token in (
            "likes",
            "comments",
            "views",
            "shares",
            "engagement",
            "avg",
            "posts/day",
            "cadence",
        )
    )
    has_digit = any(ch.isdigit() for ch in t)
    colon_scoreboard = ":" in t and has_digit
    return colon_scoreboard or (metricish and has_digit)


async def _maybe_image(
    provider: LLMProvider,
    brief: str,
    brand: str,
    *,
    aspect_ratio: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    try:
        image = await provider.generate_image(
            brief,
            style_hints=[brand, "electric lime accents", "dark editorial"],
            aspect_ratio=aspect_ratio,
        )
        return image.mime_type, base64.b64encode(image.data).decode("ascii"), None
    except LLMProviderError as exc:
        logger.warning("creative generate_image failed; caption-only: %s", exc.detail)
        return None, None, exc.detail
    except Exception:  # noqa: BLE001
        logger.warning("creative generate_image failed; caption-only", exc_info=True)
        return None, None, "Nano Banana 2 did not return an image. Try Generate again."


async def generate_creative(request: CreativeRequest, provider: LLMProvider) -> CreativeResponse:
    report_excerpt = (request.report_markdown or "")[:3500]
    voice = request.voice_notes or "on-brand, sharp, human"
    # Memes need denser scout receipts (cadence, format mix, rival heat) without naming rivals in-frame.
    facts_cap = 9000 if (request.format or "") == "meme" else 7000 if request.kind == "studio" else 4000
    facts = (request.facts_json or "")[:facts_cap]
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
        variant_line = ""
        if request.variant_count > 1 or request.variant > 1:
            variant_line = (
                f"Batch variant {request.variant} of {request.variant_count}: "
                "make a DISTINCT angle/punchline from other variants in this batch.\n"
            )
        dossier = _brand_dossier_lines(request)
        if fmt == "meme":
            user = (
                f"{dossier}\n"
                f"Platform: {platform} crop {crop}\n"
                f"Format: meme\nSpec: {spec}\n"
                f"Spice: {request.spice}/5 ({_spice_label(request.spice)}) — "
                "at spice ≥ 4 the meme MUST feel HARD Gen-Z chaotic, not a corporate still.\n"
                f"{variant_line}"
                "MISSION: invent a CRAZY visual metaphor that roasts a SPECIFIC rival flaw.\n"
                "ROAST_PACK is intelligence FUEL only — who to dunk and why. "
                "Do NOT paint the JSON. Do NOT put metrics in the overlay "
                '(banned patterns: "Rival: 18 Likes", "0 Comments", scoreboard comparisons).\n'
                "Overlay = punchline joke (3–6 words). Caption may cite one real receipt number.\n"
                "image_brief = absurdist metaphor still. BANNED frames: laptop, dashboard, charts, "
                "Wi-Fi icon, coffee-cup war room, neon hacker desk, soft founder portrait.\n"
                "Stay about the rival's real weakness from the pack — not a random unrelated bit.\n"
                f"ROAST_PACK:\n{facts or report_excerpt}\n"
            )
        else:
            user = (
                f"{dossier}\n"
                f"Platform: {platform} crop {crop}\n"
                f"Format: {fmt}\nSpec: {spec}\n"
                f"Spice: {request.spice}/5 ({_spice_label(request.spice)})\n"
                f"{variant_line}"
                "Use brand voice + scout facts (companies, platforms, cadence, formatMix, "
                "winning/leaking, topPosts captions/heat). Never put rival logos in image_brief.\n"
                f"Facts:\n{facts or report_excerpt}\n"
            )
        raw = await provider.complete(
            [Message(role="system", content=director), Message(role="user", content=user)],
            temperature=_meme_temperature(request.spice) if fmt == "meme" else 0.85,
            max_tokens=700,
        )
        try:
            data = parse_json_object(raw)
        except Exception:  # noqa: BLE001
            data = {
                "caption": raw.strip(),
                "image_brief": raw.strip(),
                "why_slaps": "",
                "overlay_text": "",
                "hashtags": [],
            }
        caption = await voice_guard(
            str(data.get("caption") or "").strip(),
            forbidden=request.forbidden_claims,
            provider=provider,
        )
        overlay = " ".join(str(data.get("overlay_text") or "").split())[:80]
        if fmt == "meme" and _looks_like_metric_overlay(overlay):
            # One retry when the model slips into scoreboard overlays.
            retry_user = (
                f"{user}\n"
                f"REJECTED overlay (too metric/scoreboard): {overlay!r}\n"
                "Rewrite with a HARD absurdist punchline. No digits-as-scoreboard. "
                "No 'Brand: N Likes'. Keep the roast about the same rival flaw.\n"
            )
            raw2 = await provider.complete(
                [Message(role="system", content=director), Message(role="user", content=retry_user)],
                temperature=min(1.3, _meme_temperature(request.spice) + 0.1),
                max_tokens=700,
            )
            try:
                data2 = parse_json_object(raw2)
                caption = await voice_guard(
                    str(data2.get("caption") or caption).strip(),
                    forbidden=request.forbidden_claims,
                    provider=provider,
                )
                overlay2 = " ".join(str(data2.get("overlay_text") or "").split())[:80]
                if overlay2 and not _looks_like_metric_overlay(overlay2):
                    overlay = overlay2
                    data = data2
            except Exception:  # noqa: BLE001
                pass
        image_brief = str(data.get("image_brief") or caption)
        if fmt == "meme":
            brief = (
                f"{image_brief}\n"
                f"Aspect {crop}. HARD Gen-Z meme still — absurdist metaphor, NOT a workplace photo. "
                f'Render EXACT overlay text letter-perfect: "{overlay or "no text"}". '
                "Do not invent additional words. Do not draw charts, laptops, or dashboards. "
                f"{IMAGE_NEGATIVES}"
            )
        else:
            brief = (
                f"{image_brief}\nAspect {crop}. Single frame. Overlay: "
                f"{overlay or 'none'}. {IMAGE_NEGATIVES}"
            )
        concept = image_brief or caption or "lime-on-black editorial still"
        mime, b64, image_error = await _maybe_image(
            provider, brief, request.brand_name, aspect_ratio=crop
        )
        raw_tags = data.get("hashtags")
        tags = [str(t) for t in raw_tags][:3] if isinstance(raw_tags, list) else []
        return CreativeResponse(
            kind="studio",
            text=caption or concept,
            image_concept=concept,
            image_mime_type=mime,
            image_data_base64=b64,
            image_error=image_error,
            why_slaps=str(data.get("why_slaps") or "") or None,
            overlay_text=overlay or None,
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
    mime, b64, image_error = await _maybe_image(
        provider, brief, request.brand_name, aspect_ratio="1:1"
    )
    return CreativeResponse(
        kind="image",
        text=concept.strip(),
        image_concept=concept.strip(),
        image_mime_type=mime,
        image_data_base64=b64,
        image_error=image_error,
    )
