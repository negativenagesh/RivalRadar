from app.creative import CreativeRequest, generate_creative
from app.intel import IntelRequest, fallback_intel, generate_intel

from tests.fakes import FakeLLMProvider


async def test_generate_intel_from_json() -> None:
    provider = FakeLLMProvider(
        completion=(
            '{"scoreboard_blurb":"you vs them",'
            '"markdown":"# Intel brief\\n\\n## Heat\\n- they post 4 memes",'
            '"good_at":["hooks"],"fumbling":["cadence"],'
            '"why_engagement_mid":["0.4 posts/day"],"gaps":["memes"],'
            '"plays":[{"title":"meme the gap","format":"meme","platform":"instagram",'
            '"why":"they post 4 memes"}],'
            '"sniper_bait":[{"why":"weak comments","href":"https://x.com/a/status/1","company":"rival"}],'
            '"reports":[{"id":"plays","title":"This week\'s plays","markdown":"## Plays\\n- meme the gap"}]}'
        )
    )
    report = await generate_intel(
        IntelRequest(facts={"leakingBecause": ["cadence"]}, brand_name="Pixis"),
        provider,
    )
    assert report.scoreboard_blurb == "you vs them"
    assert "# Intel brief" in report.markdown
    assert report.plays[0].format == "meme"
    assert report.sniper_bait[0].href.startswith("https://")
    assert report.reports[0].id == "plays"


async def test_fallback_intel_writes_pointwise_markdown() -> None:
    report = fallback_intel(
        {
            "window": {"label": "last 3 days"},
            "companies": [{"name": "Pixis", "role": "brand", "posts": 2, "avgEngagement": 4}],
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
    assert len(report.reports) == 3


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
