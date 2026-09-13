from __future__ import annotations

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field

from app.agents.parse import parse_json_object
from app.agents.prompts import INTEL_CHIEF, PLAY_CALLER, PLAY_CALLER_HINT
from llm_provider import LLMProvider, Message


class IntelPlay(BaseModel):
    title: str
    format: str
    platform: str
    why: str


class SniperBait(BaseModel):
    why: str
    href: str
    company: str


class IntelSection(BaseModel):
    id: str
    title: str
    markdown: str


class IntelReport(BaseModel):
    scoreboard_blurb: str
    markdown: str = ""
    reports: list[IntelSection] = Field(default_factory=list)
    good_at: list[str] = Field(default_factory=list)
    fumbling: list[str] = Field(default_factory=list)
    why_engagement_mid: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    plays: list[IntelPlay] = Field(default_factory=list)
    sniper_bait: list[SniperBait] = Field(default_factory=list)


class IntelRequest(BaseModel):
    facts: dict[str, Any]
    brand_name: str = "the brand"
    voice_notes: str = ""
    forbidden_claims: str = ""


def _str_list(value: object, limit: int = 8) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _bullets(lines: list[str], empty: str) -> str:
    if not lines:
        return f"- {empty}"
    return "\n".join(f"- {line}" for line in lines)


def facts_to_markdown(facts: dict[str, Any], brand_name: str) -> str:
    window = facts.get("window") or {}
    label = window.get("label") if isinstance(window, dict) else None
    companies = facts.get("companies") if isinstance(facts.get("companies"), list) else []
    mix = facts.get("formatMix") if isinstance(facts.get("formatMix"), list) else []
    winning = _str_list(facts.get("winningBecause"), 8)
    leaking = _str_list(facts.get("leakingBecause"), 8)
    top = facts.get("topPosts") if isinstance(facts.get("topPosts"), list) else []
    sniper = facts.get("sniperQueue") if isinstance(facts.get("sniperQueue"), list) else []

    company_lines: list[str] = []
    for row in companies[:8]:
        if not isinstance(row, dict):
            continue
        role = "you" if row.get("role") == "brand" else "rival"
        company_lines.append(
            f"**{row.get('name', 'unknown')}** ({role}): {row.get('posts', 0)} posts, "
            f"avg heat {row.get('avgEngagement', 0)}"
        )

    mix_lines: list[str] = []
    for row in mix[:8]:
        if not isinstance(row, dict):
            continue
        mix_lines.append(
            f"**{row.get('format', 'unknown')}** is {row.get('pct', 0)}% of the window "
            f"({row.get('count', 0)} posts)"
        )

    receipt_lines: list[str] = []
    for row in top[:5]:
        if not isinstance(row, dict):
            continue
        href = str(row.get("href") or "").strip()
        label_text = (
            f"{row.get('company')} on {row.get('platform')}: {row.get('likes', 0)}♡ / "
            f"{row.get('comments', 0)}💬 — {(str(row.get('caption') or '')[:90])}"
        )
        receipt_lines.append(f"[{label_text}]({href})" if href else label_text)

    sniper_lines: list[str] = []
    for row in sniper[:6]:
        if not isinstance(row, dict):
            continue
        href = str(row.get("href") or "").strip()
        text = (
            f"{row.get('company')} · {row.get('platform')} · {row.get('likes', 0)}♡ / "
            f"{row.get('comments', 0)}💬"
        )
        sniper_lines.append(f"[{text}]({href})" if href else text)

    play_fmt = "founder_post"
    play_pct = 0
    if mix and isinstance(mix[0], dict):
        play_fmt = str(mix[0].get("format") or play_fmt)
        play_pct = int(mix[0].get("pct") or 0)

    return "\n".join(
        [
            f"# Intel brief — {brand_name}",
            "",
            f"Window: **{label or 'this lookback'}**. Numbers are from the scout, not vibes.",
            "",
            "## Scoreboard",
            _bullets(company_lines, "Zero in-window posts — scout this lookback first."),
            "",
            "## What you're actually good at",
            _bullets(winning, "Scout more; the board is still loading."),
            "",
            "## What you're fumbling",
            _bullets(
                leaking,
                "No obvious leaks in this window — you're keeping pace."
                if companies
                else "Not enough in-window posts to roast you yet.",
            ),
            "",
            "## Why engagement is mid",
            _bullets(leaking[:4] or winning[:3], "Need more in-window posts before we call the heat."),
            "",
            "## Gaps they own",
            _bullets(leaking[-3:] or mix_lines[:3], "No gap call until the mix fills in."),
            "",
            "## Format mix",
            _bullets(mix_lines, "No format mix yet — the window is empty."),
            "",
            "## This week's plays",
            _bullets(
                [
                    f"Lean into **{play_fmt}** — it's {play_pct}% of what the feed already rewards.",
                    "Ship one visual every post. Text-only gets ghosted.",
                    "Comment on the hottest rival permalinks in the sniper docket — human approve, one at a time.",
                    "Don't invent metrics in public. Cite the receipts below or stay quiet.",
                ],
                "No play until there are posts.",
            ),
            "",
            "## Receipts we can cite",
            _bullets(receipt_lines, "No permalinks in this window."),
            "",
            "## Sniper docket",
            _bullets(sniper_lines, "No rival permalinks queued."),
        ]
    )


def _fallback_reports(facts: dict[str, Any], brand_name: str) -> list[IntelSection]:
    mix = facts.get("formatMix") if isinstance(facts.get("formatMix"), list) else []
    sniper = facts.get("sniperQueue") if isinstance(facts.get("sniperQueue"), list) else []
    mix_lines = []
    for row in mix[:10]:
        if isinstance(row, dict):
            mix_lines.append(
                f"- **{row.get('format')}** — {row.get('count', 0)} posts ({row.get('pct', 0)}%)"
            )
    sniper_lines = []
    for row in sniper[:8]:
        if not isinstance(row, dict):
            continue
        href = str(row.get("href") or "").strip()
        line = (
            f"**{row.get('company')}** on {row.get('platform')} · "
            f"{row.get('likes', 0)} likes / {row.get('comments', 0)} comments"
        )
        sniper_lines.append(f"- [{line}]({href})" if href else f"- {line}")
    return [
        IntelSection(
            id="plays",
            title="This week's plays",
            markdown="\n".join(
                [
                    f"## Plays for {brand_name}",
                    "- Steal the room's dominant format, not their caption.",
                    "- One visual per post. Algorithms ghost walls of text.",
                    "- One sniper comment after a human hits Approve — never a spray.",
                    "- Quote a real receipt (likes / comments / cadence) or don't dunk.",
                    "- Keep forbidden claims out of the overlay and the caption.",
                    "- If cadence is thin, post before you roast.",
                    "- Trend-jack themes, not their words.",
                    "- End LinkedIn on a question people will actually answer.",
                ]
            ),
        ),
        IntelSection(
            id="format",
            title="Format mix roast",
            markdown="\n".join(
                [
                    "## Format mix roast",
                    *(mix_lines or ["- Window is empty — no mix to roast yet."]),
                    "- Double down on whatever already has heat in this window.",
                    "- If memes are missing and the room is meme-heavy, that's the gap.",
                    "- Carousels without a hook slide are just PDFs in a trench coat.",
                ]
            ),
        ),
        IntelSection(
            id="sniper",
            title="Sniper docket",
            markdown="\n".join(
                [
                    "## Sniper docket",
                    *(sniper_lines or ["- No rival permalinks in this window."]),
                    "- Human delays 10–15s. One hop. You approved this.",
                    "- YouTube comments stay out of scope.",
                ]
            ),
        ),
    ]


def fallback_intel(facts: dict[str, Any], brand_name: str) -> IntelReport:
    leaking = _str_list(facts.get("leakingBecause"), 5)
    winning = _str_list(facts.get("winningBecause"), 5)
    sniper: list[SniperBait] = []
    for item in (facts.get("sniperQueue") or [])[:5]:
        if not isinstance(item, dict):
            continue
        href = str(item.get("href") or "")
        if not href:
            continue
        sniper.append(
            SniperBait(
                why=f"Heat on {item.get('platform')}: {item.get('likes', 0)} likes / {item.get('comments', 0)} comments",
                href=href,
                company=str(item.get("company") or "rival"),
            )
        )
    plays: list[IntelPlay] = []
    mix = facts.get("formatMix") or []
    if isinstance(mix, list) and mix and isinstance(mix[0], dict):
        plays.append(
            IntelPlay(
                title=f"Lean into {mix[0].get('format', 'founder_post')}",
                format=str(mix[0].get("format") or "founder_post"),
                platform="linkedin",
                why=f"It's {mix[0].get('pct', 0)}% of the window — that's the language the feed already speaks.",
            )
        )
    companies = facts.get("companies") or []
    return IntelReport(
        scoreboard_blurb=f"{brand_name} vs the room — numbers first, vibes second.",
        markdown=facts_to_markdown(facts, brand_name),
        reports=_fallback_reports(facts, brand_name),
        good_at=winning or ["Scout more; the board is still loading."],
        fumbling=leaking
        or (
            ["No obvious leaks in this window — you're keeping pace."]
            if companies
            else ["Not enough in-window posts to roast you yet."]
        ),
        why_engagement_mid=leaking[:3],
        gaps=leaking[-2:],
        plays=plays,
        sniper_bait=sniper,
    )


def _nonzero(value: object) -> bool:
    if value is None:
        return False
    if value == "":
        return False
    if value == []:
        return False
    if value == {}:
        return False
    return True


def _merge_intel(fallback: IntelReport, data: dict[str, Any]) -> IntelReport:
    base = fallback.model_dump()
    for key, value in data.items():
        if key == "reports":
            continue
        if _nonzero(value):
            base[key] = value
    reports = _reports_from(data, fallback.reports)
    base["reports"] = [section.model_dump() for section in reports]
    if not str(base.get("markdown") or "").strip():
        base["markdown"] = fallback.markdown
    return IntelReport.model_validate(base)


def _reports_from(data: dict[str, Any], fallback: list[IntelSection]) -> list[IntelSection]:
    raw = data.get("reports")
    if not isinstance(raw, list) or not raw:
        return fallback
    out: list[IntelSection] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        markdown = str(item.get("markdown") or "").strip()
        if not markdown:
            continue
        out.append(
            IntelSection(
                id=str(item.get("id") or f"r{len(out)}"),
                title=str(item.get("title") or "Brief"),
                markdown=markdown,
            )
        )
    return out or fallback


async def _complete_json(
    provider: LLMProvider,
    *,
    system: str,
    user: str,
    max_tokens: int,
) -> dict[str, Any]:
    try:
        raw = await provider.complete(
            [Message(role="system", content=system), Message(role="user", content=user)],
            temperature=0.3,
            max_tokens=max_tokens,
            reasoning_effort="low",
        )
        return parse_json_object(raw)
    except Exception:  # noqa: BLE001
        return {}


async def generate_intel(request: IntelRequest, provider: LLMProvider) -> IntelReport:
    facts = request.facts or {}
    fallback = fallback_intel(facts, request.brand_name)
    packed = json.dumps(facts, ensure_ascii=False)[:16000]
    header = (
        f"Brand: {request.brand_name}\n"
        f"Voice: {request.voice_notes or 'sharp, human'}\n"
        f"Forbidden: {request.forbidden_claims or 'none listed'}\n"
        f"{PLAY_CALLER_HINT}\n\n"
        f"FACTS (source of truth):\n{packed}"
    )
    chief_user = (
        "JSON schema keys: scoreboard_blurb, markdown, "
        "good_at[], fumbling[], why_engagement_mid[], gaps[], "
        "plays[{title,format,platform,why}], sniper_bait[{why,href,company}].\n\n"
        f"{header}"
    )
    play_user = header
    chief_data, play_data = await asyncio.gather(
        _complete_json(provider, system=INTEL_CHIEF, user=chief_user, max_tokens=3500),
        _complete_json(provider, system=PLAY_CALLER, user=play_user, max_tokens=2200),
    )
    merged = dict(chief_data)
    if isinstance(play_data.get("reports"), list) and play_data["reports"]:
        merged["reports"] = play_data["reports"]
    elif isinstance(chief_data.get("reports"), list) and chief_data["reports"]:
        merged["reports"] = chief_data["reports"]
    return _merge_intel(fallback, merged)
