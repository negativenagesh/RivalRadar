from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.parse import parse_json_object
from app.agents.prompts import (
    INTEL_CHIEF,
    PLATFORM_SCOUT,
    PLAY_CALLER,
    PLAY_CALLER_HINT,
)
from llm_provider import LLMProvider, Message

logger = logging.getLogger(__name__)

_REQUIRED_HEADINGS = (
    "scoreboard",
    "good at",
    "fumbling",
    "engagement",
    "gaps",
    "platform",
    "format",
    "plays",
    "receipts",
    "sniper",
)


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
    agents_used: list[str] = Field(default_factory=list)
    narration: Literal["agent", "fallback"] = "fallback"


class IntelRequest(BaseModel):
    facts: dict[str, Any]
    brand_name: str = "the brand"
    voice_notes: str = ""
    forbidden_claims: str = ""


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _str_list(value: object, limit: int = 8) -> list[str]:
    out: list[str] = []
    for item in _as_list(value):
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


def _platforms_in_facts(facts: dict[str, Any]) -> list[str]:
    seen: list[str] = []
    for company in _as_list(facts.get("companies")):
        if not isinstance(company, dict):
            continue
        for row in _as_list(company.get("platforms")):
            if not isinstance(row, dict):
                continue
            plat = str(row.get("platform") or "").strip().lower()
            if plat and plat not in seen:
                seen.append(plat)
    return seen


def _platform_eval_lines(facts: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for company in _as_list(facts.get("companies")):
        if not isinstance(company, dict):
            continue
        name = str(company.get("name") or "unknown")
        role = "you" if company.get("role") == "brand" else "rival"
        for row in _as_list(company.get("platforms")):
            if not isinstance(row, dict):
                continue
            lines.append(
                f"**{name}** ({role}) on **{row.get('platform')}**: "
                f"{row.get('posts', 0)} posts · cadence {row.get('cadencePerDay', 0)}/day · "
                f"avg {row.get('avgLikes', 0)}♡ / {row.get('avgComments', 0)}💬 · "
                f"comment-rate {row.get('commentRate', 0)}%"
            )
    return lines


def facts_to_markdown(facts: dict[str, Any], brand_name: str) -> str:
    window = facts.get("window") or {}
    label = window.get("label") if isinstance(window, dict) else None
    companies = _as_list(facts.get("companies"))
    mix = _as_list(facts.get("formatMix"))
    winning = _str_list(facts.get("winningBecause"), 8)
    leaking = _str_list(facts.get("leakingBecause"), 8)
    top = _as_list(facts.get("topPosts"))
    sniper = _as_list(facts.get("sniperQueue"))
    platform_lines = _platform_eval_lines(facts)

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

    # Keep section bullets distinct even in the offline fact brief.
    fumbling = leaking[:3] or winning[:2]
    why_mid = leaking[1:4] or mix_lines[:2] or fumbling[:2]
    gaps = leaking[2:5] or platform_lines[:3] or mix_lines[:2]

    return "\n".join(
        [
            f"# Intel brief — {brand_name}",
            "",
            f"Window: **{label or 'this lookback'}**. Numbers are from the scout, not vibes.",
            "",
            "## Scoreboard read",
            _bullets(
                [
                    *company_lines,
                    "This is the offline fact brief — paste a text model key so Intel Chief can evaluate, not just reprint.",
                ]
                if company_lines
                else [],
                "Zero in-window posts — scout this lookback first.",
            ),
            "",
            "## What you're actually good at",
            _bullets(winning, "Scout more; the board is still loading."),
            "",
            "## What you're fumbling",
            _bullets(
                fumbling,
                "No obvious leaks in this window — you're keeping pace."
                if companies
                else "Not enough in-window posts to roast you yet.",
            ),
            "",
            "## Why engagement is mid",
            _bullets(why_mid, "Need more in-window posts before we call the heat."),
            "",
            "## Gaps they own",
            _bullets(gaps, "No gap call until the mix fills in."),
            "",
            "## Platform evals",
            _bullets(platform_lines, "No platform stats in this window."),
            "",
            "## Format & creative read",
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
    mix = _as_list(facts.get("formatMix"))
    sniper = _as_list(facts.get("sniperQueue"))
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
    platform_lines = [f"- {line}" for line in _platform_eval_lines(facts)]
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
        IntelSection(
            id="platforms",
            title="Platform evals",
            markdown="\n".join(
                [
                    "## Platform evals",
                    *(platform_lines or ["- No platform stats yet — scout first."]),
                    "- Treat each platform as its own arena: cadence, heat, and comment rate.",
                ]
            ),
        ),
        IntelSection(
            id="competitive",
            title="Head-to-head",
            markdown="\n".join(
                [
                    f"## Head-to-head — {brand_name}",
                    *(platform_lines[:8] or ["- Need rival + brand posts in-window."]),
                    "- Steal the move that already has heat; don't invent a new language.",
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
        why_engagement_mid=leaking[1:4] or leaking[:3],
        gaps=leaking[2:5] or leaking[-2:],
        plays=plays,
        sniper_bait=sniper,
        agents_used=[],
        narration="fallback",
    )


def _nonzero(value: object) -> bool:
    return value not in (None, "", [], {})


def _bullet_lines(markdown: str) -> list[str]:
    return [
        line.strip().lstrip("-* ").strip().lower()
        for line in (markdown or "").splitlines()
        if line.strip().startswith(("-", "*"))
    ]


def markdown_passes_quality(candidate: str, *, fallback: str, platforms: list[str]) -> bool:
    """Reject empty / template-clone / thin agent output so we can retry or fall back."""
    text = (candidate or "").strip()
    if len(text) < 500:
        return False
    low = text.lower()
    if not low.startswith("# intel brief"):
        return False
    heading_hits = sum(1 for needle in _REQUIRED_HEADINGS if needle in low)
    if heading_hits < 6:
        return False
    bullets = _bullet_lines(text)
    if len(bullets) < 16:
        return False
    unique = {b for b in bullets if len(b) > 12}
    if len(unique) < 12:
        return False
    fb_bullets = set(_bullet_lines(fallback))
    if fb_bullets:
        overlap = len(unique & fb_bullets) / max(1, len(unique))
        if overlap > 0.55:
            return False
    if platforms:
        covered = sum(1 for p in platforms if p in low)
        if covered < max(1, min(len(platforms), 2)):
            return False
    return True


def _merge_intel(
    fallback: IntelReport,
    data: dict[str, Any],
    *,
    agents_used: list[str],
    narration: Literal["agent", "fallback"],
) -> IntelReport:
    base = fallback.model_dump()
    for key, value in data.items():
        if key in {"reports", "agents_used", "narration"}:
            continue
        if _nonzero(value):
            base[key] = value
    reports = _reports_from(data, fallback.reports)
    base["reports"] = [section.model_dump() for section in reports]
    if not str(base.get("markdown") or "").strip():
        base["markdown"] = fallback.markdown
    base["agents_used"] = agents_used
    base["narration"] = narration
    return IntelReport.model_validate(base)


def _reports_from(data: dict[str, Any], fallback: list[IntelSection]) -> list[IntelSection]:
    raw = data.get("reports")
    if not isinstance(raw, list) or not raw:
        return fallback
    by_id = {section.id: section for section in fallback}
    for item in raw:
        if not isinstance(item, dict):
            continue
        markdown = str(item.get("markdown") or "").strip()
        if not markdown:
            continue
        section_id = str(item.get("id") or f"r{len(by_id)}")
        by_id[section_id] = IntelSection(
            id=section_id,
            title=str(item.get("title") or by_id.get(section_id, IntelSection(id=section_id, title="Brief", markdown="")).title),
            markdown=markdown,
        )
    # Keep a stable order: plays, format, sniper, platforms, competitive, then extras.
    order = ["plays", "format", "sniper", "platforms", "competitive"]
    ordered: list[IntelSection] = []
    seen: set[str] = set()
    for key in order:
        if key in by_id:
            ordered.append(by_id[key])
            seen.add(key)
    for key, section in by_id.items():
        if key not in seen:
            ordered.append(section)
    return ordered or fallback


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
            temperature=0.35,
            max_tokens=max_tokens,
            reasoning_effort="low",
        )
        return parse_json_object(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("intel agent JSON parse/complete failed: %s", exc)
        return {}


def _facts_header(request: IntelRequest, facts: dict[str, Any]) -> str:
    platforms = _platforms_in_facts(facts)
    packed = json.dumps(facts, ensure_ascii=False)[:18000]
    must = ", ".join(platforms) if platforms else "none yet"
    return (
        f"Brand: {request.brand_name}\n"
        f"Voice: {request.voice_notes or 'sharp, human'}\n"
        f"Forbidden: {request.forbidden_claims or 'none listed'}\n"
        f"{PLAY_CALLER_HINT}\n"
        f"MUST evaluate platforms: {must}\n\n"
        f"FACTS (source of truth — evaluate, do not reprint):\n{packed}"
    )


async def generate_intel(request: IntelRequest, provider: LLMProvider) -> IntelReport:
    facts = request.facts or {}
    fallback = fallback_intel(facts, request.brand_name)
    platforms = _platforms_in_facts(facts)
    header = _facts_header(request, facts)
    chief_user = (
        "JSON schema keys: scoreboard_blurb, markdown, "
        "good_at[], fumbling[], why_engagement_mid[], gaps[], "
        "plays[{title,format,platform,why}], sniper_bait[{why,href,company}].\n\n"
        f"{header}"
    )
    play_user = header
    platform_user = header

    chief_data, play_data, platform_data = await asyncio.gather(
        _complete_json(provider, system=INTEL_CHIEF, user=chief_user, max_tokens=4500),
        _complete_json(provider, system=PLAY_CALLER, user=play_user, max_tokens=2800),
        _complete_json(provider, system=PLATFORM_SCOUT, user=platform_user, max_tokens=3200),
    )

    agents_used: list[str] = []
    if chief_data:
        agents_used.append("intel_chief")
    if play_data.get("reports"):
        agents_used.append("play_caller")
    if platform_data.get("reports"):
        agents_used.append("platform_scout")

    # One retry if chief markdown is thin / template-clone (common with gpt-oss empty JSON).
    markdown = str(chief_data.get("markdown") or "").strip()
    if not markdown_passes_quality(markdown, fallback=fallback.markdown, platforms=platforms):
        retry_user = (
            chief_user
            + "\n\nRETRY: Your previous draft failed quality. "
            "Write a NEW evaluative brief with 25+ distinct bullets. "
            "Do not copy FACTS lines. Cover every MUST-evaluate platform."
        )
        retry = await _complete_json(
            provider, system=INTEL_CHIEF, user=retry_user, max_tokens=4500
        )
        if retry:
            chief_data = {**chief_data, **retry}
            markdown = str(chief_data.get("markdown") or "").strip()
            if "intel_chief" not in agents_used:
                agents_used.append("intel_chief")

    merged: dict[str, Any] = dict(chief_data)
    report_chunks: list[Any] = []
    for blob in (play_data, platform_data, chief_data):
        raw = blob.get("reports")
        if isinstance(raw, list):
            report_chunks.extend(raw)
    if report_chunks:
        merged["reports"] = report_chunks

    agent_ok = markdown_passes_quality(
        str(merged.get("markdown") or ""),
        fallback=fallback.markdown,
        platforms=platforms,
    )
    if not agent_ok:
        # Keep structured fields / agent reports if present, but stick to fact markdown.
        merged.pop("markdown", None)
        narration: Literal["agent", "fallback"] = "fallback"
        if not agents_used:
            agents_used = []
        logger.info("intel chief markdown failed quality gate — using fact brief + agent tabs if any")
    else:
        narration = "agent"

    return _merge_intel(fallback, merged, agents_used=agents_used, narration=narration)
