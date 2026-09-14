from app.creative import CreativeRequest, generate_creative
from app.intel import (
    IntelRequest,
    fallback_intel,
    generate_intel,
    markdown_passes_quality,
)

from tests.fakes import FakeLLMProvider
import json

_RICH_BRIEF = """# Intel brief — Pixis

## Scoreboard read
- Pixis (you) is at 1 post / avg heat 20 while Smartly (rival) holds 4 posts / 14.3 — volume is their edge, not heat.
- LinkedIn is the only arena with real receipts this window; treat IG as a secondary board.

## What you're actually good at
- Your LinkedIn founder_post landed 15♡ — competitive heat vs Smartly's pack average.
- Window mix is 100% founder_post (5 posts) — you already speak the room's language.

## What you're fumbling
- Cadence 0.1 posts/day vs their 0.3 — you go dark between drops.
- Comment rate is flat (0💬 across the board) — hooks aren't earning replies.

## Why engagement is mid
- Sparse cadence means each post has to work alone; theirs stack in the feed.
- Text-first captions without a visual ask the algo to do charity.

## Gaps they own
- Smartly owns LinkedIn volume (3 posts, avg 15.7♡) while you ship once.
- Their ADVANCE / Roku partner beat is a stealable proof format you didn't answer.

## Platform evals
- linkedin: Pixis 1 post / 15♡; Smartly 3 posts / 15.7♡ avg — match cadence before you match punchlines.
- instagram: Smartly has a thin IG receipt (0♡ logged) — don't chase empty boards.
- x: no in-window receipts — skip sniper there this week.

## Format & creative read
- founder_post is 100% of the window — lean in, don't invent a meme lane from nothing.

## This week's plays
- Ship 2 LinkedIn founder posts with one visual each before roasting anyone.
- Comment on Smartly's hottest permalink after human Approve.

## Receipts we can cite
- Smartly LinkedIn 26♡ partner beat — real heat to answer, not ignore.

## Sniper docket
- Smartly LinkedIn 26♡ / 0💬 and 18♡ / 0💬 — human approve, one hop.
"""


async def test_generate_intel_from_json() -> None:
    payload = {
        "scoreboard_blurb": "you vs them",
        "markdown": _RICH_BRIEF,
        "good_at": ["hooks"],
        "fumbling": ["cadence"],
        "why_engagement_mid": ["0.4 posts/day"],
        "gaps": ["memes"],
        "plays": [
            {
                "title": "meme the gap",
                "format": "meme",
                "platform": "instagram",
                "why": "they post 4 memes",
            }
        ],
        "sniper_bait": [
            {
                "why": "weak comments",
                "href": "https://x.com/a/status/1",
                "company": "rival",
            }
        ],
        "reports": [
            {
                "id": "plays",
                "title": "This week's plays",
                "markdown": "## Plays\n- meme the gap",
            }
        ],
    }
    provider = FakeLLMProvider(completion=json.dumps(payload))
    report = await generate_intel(
        IntelRequest(
            facts={
                "leakingBecause": ["cadence"],
                "companies": [
                    {
                        "name": "Pixis",
                        "role": "brand",
                        "posts": 1,
                        "avgEngagement": 20,
                        "platforms": [
                            {
                                "platform": "linkedin",
                                "posts": 1,
                                "avgLikes": 15,
                                "avgComments": 0,
                                "cadencePerDay": 0.1,
                                "commentRate": 0,
                            }
                        ],
                    },
                    {
                        "name": "Smartly",
                        "role": "rival",
                        "posts": 4,
                        "avgEngagement": 14,
                        "platforms": [
                            {
                                "platform": "linkedin",
                                "posts": 3,
                                "avgLikes": 15.7,
                                "avgComments": 0,
                                "cadencePerDay": 0.3,
                                "commentRate": 0,
                            },
                            {
                                "platform": "instagram",
                                "posts": 1,
                                "avgLikes": 0,
                                "avgComments": 0,
                                "cadencePerDay": 0.1,
                                "commentRate": 0,
                            },
                        ],
                    },
                ],
            },
            brand_name="Pixis",
        ),
        provider,
    )
    assert report.scoreboard_blurb == "you vs them"
    assert "# Intel brief" in report.markdown
    assert "## Platform evals" in report.markdown
    assert report.plays[0].format == "meme"
    assert report.sniper_bait[0].href.startswith("https://")
    assert report.reports[0].id == "plays"
    assert report.narration == "agent"
    assert "intel_chief" in report.agents_used
    assert provider.complete_calls >= 3


async def test_fallback_intel_writes_pointwise_markdown() -> None:
    report = fallback_intel(
        {
            "window": {"label": "last 3 days"},
            "companies": [
                {
                    "name": "Pixis",
                    "role": "brand",
                    "posts": 2,
                    "avgEngagement": 4,
                    "platforms": [
                        {
                            "platform": "linkedin",
                            "posts": 2,
                            "avgLikes": 4,
                            "avgComments": 0,
                            "avgShares": 0,
                            "avgViews": 0,
                            "commentRate": 0,
                            "cadencePerDay": 0.7,
                        }
                    ],
                }
            ],
            "formatMix": [{"format": "founder_post", "count": 2, "pct": 100}],
            "winningBecause": ["hooks"],
            "leakingBecause": ["cadence"],
            "topPosts": [],
            "sniperQueue": [],
        },
        "Pixis",
    )
    assert report.markdown.startswith("# Intel brief")
    assert "## What you're fumbling" in report.markdown
    assert "## Platform evals" in report.markdown
    assert len(report.reports) == 5
    assert report.narration == "fallback"


def test_markdown_quality_rejects_template_clone() -> None:
    fallback = fallback_intel(
        {
            "window": {"label": "last 7 days"},
            "companies": [],
            "formatMix": [],
            "winningBecause": [],
            "leakingBecause": ["Cadence 0.1 posts/day vs their 0.3 — you go dark, they stay in the feed"],
            "topPosts": [],
            "sniperQueue": [],
        },
        "Pixis",
    ).markdown
    assert not markdown_passes_quality(fallback, fallback=fallback, platforms=["linkedin"])
    assert markdown_passes_quality(_RICH_BRIEF, fallback=fallback, platforms=["linkedin", "instagram"])


async def test_generate_studio_creative_parses_json() -> None:
    provider = FakeLLMProvider(
        completion=(
            '{"caption":"we shipped the boring thing first",'
            '"overlay_text":"ship the boring",'
            '"why_slaps":"their carousel ate 40% of the mix",'
            '"hashtags":["build"],"image_brief":"lime on black founder at 2am"}'
        )
    )
    result = await generate_creative(
        CreativeRequest(
            kind="studio",
            brand_name="Pixis",
            format="hot_take",
            platform="instagram",
            spice=4,
            facts_json='{"formatMix":[{"format":"carousel","pct":40}]}',
        ),
        provider,
    )
    assert result.kind == "studio"
    assert "boring" in result.text
    assert result.overlay_text == "ship the boring"
    assert result.why_slaps
    assert result.image_data_base64
    assert provider.complete_calls == 1
    assert provider.last_aspect_ratio == "4:5"


async def test_studio_surfaces_image_error_when_nano_banana_fails() -> None:
    provider = FakeLLMProvider(
        completion='{"caption":"ok","overlay_text":"go","why_slaps":"receipt","hashtags":[],"image_brief":"lime"}',
        raise_on_generate_image=True,
    )
    result = await generate_creative(
        CreativeRequest(kind="studio", brand_name="Pixis", format="meme", platform="instagram"),
        provider,
    )
    assert result.image_data_base64 is None
    assert result.image_error
    assert "Nano Banana" in (result.image_error or "")
