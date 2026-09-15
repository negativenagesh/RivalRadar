import json

from app.publish import (
    PublishPlanRequest,
    PublishVariation,
    _clean_hashtags,
    generate_publish_plan,
    publish_caption_text,
)

from tests.fakes import FakeLLMProvider


def _request(**overrides: object) -> PublishPlanRequest:
    base: dict[str, object] = {
        "brand_name": "Pixis",
        "platform": "linkedin",
        "asset_caption": "Dashboards are the new participation trophies.",
        "variations": 3,
        "facts_json": '{"brand":"Pixis","category":"adtech","rivals":["Smartly"]}',
        "image_concept": "a trophy melting into a spreadsheet waterfall",
    }
    base.update(overrides)
    return PublishPlanRequest(**base)  # type: ignore[arg-type]


async def test_publish_plan_parses_agent_hashtags_only() -> None:
    payload = {
        "variations": [
            {
                "caption": "Your rival's dashboard is a meme. Yours isn't.",
                "hashtags": [
                    "AdTech",
                    "#DashboardSlop ",
                    "#dashboardslop",
                    "#marketing",  # banned generic — dropped
                    "bad tag!!",
                    "#Growth Marketing",
                ],
                "why": "contrarian hook",
            },
            {"caption": "Second angle", "hashtags": [], "why": "question CTA"},
        ]
    }
    fake = FakeLLMProvider(completion=json.dumps(payload))
    plan = await generate_publish_plan(_request(), fake)
    assert plan.agent == "publish_strategist"
    assert len(plan.variations) == 2
    tags = plan.variations[0].hashtags
    assert tags == ["#adtech", "#dashboardslop", "#growthmarketing"]
    assert "#marketing" not in tags
    assert all(" " not in t for t in tags)


async def test_publish_plan_fallback_has_no_invented_hashtags() -> None:
    fake = FakeLLMProvider(completion="not json at all")
    plan = await generate_publish_plan(_request(platform="instagram"), fake)
    assert len(plan.variations) == 1
    assert plan.variations[0].caption
    assert plan.variations[0].hashtags == []


async def test_publish_plan_empty_agent_hashtags_stay_empty() -> None:
    payload = {
        "variations": [{"caption": "Witty take, no tags needed.", "hashtags": [], "why": "x punch"}]
    }
    fake = FakeLLMProvider(completion=json.dumps(payload))
    plan = await generate_publish_plan(_request(platform="x"), fake)
    assert plan.variations[0].hashtags == []


async def test_publish_plan_caps_caption_length_and_tag_count() -> None:
    payload = {
        "variations": [
            {
                "caption": "x" * 900,
                "hashtags": ["#adtechroast", "#pixelwar", "#third"],
                "why": "",
            }
        ]
    }
    fake = FakeLLMProvider(completion=json.dumps(payload))
    plan = await generate_publish_plan(_request(platform="x"), fake)
    assert len(plan.variations[0].caption) <= 270
    assert len(plan.variations[0].hashtags) <= 2
    assert plan.variations[0].hashtags == ["#adtechroast", "#pixelwar"]


async def test_publish_prompt_includes_image_and_facts_fuel() -> None:
    """Agent user prompt must carry image concept + brand/rival facts for hashtag fuel."""
    captured: list[str] = []

    async def _capture(messages: list[object], **_kwargs: object) -> str:
        content = str(getattr(messages[1], "content", ""))
        captured.append(content)
        if "Hashtags must be invented" in content:
            return json.dumps(
                {
                    "variations": [
                        {
                            "caption": "ok",
                            "hashtags": ["#adtechroast", "#meltedtrophy"],
                            "why": "visual",
                        }
                    ]
                }
            )
        return content  # voice-guard echo

    fake = FakeLLMProvider(completion="unused")
    fake.complete = _capture  # type: ignore[method-assign]
    await generate_publish_plan(
        _request(
            image_concept="melted trophy waterfall",
            overlay_text="participation trophy",
            asset_context="roasts Smartly dashboard theater",
            intel_markdown="## Rival cadence is vanity metrics",
        ),
        fake,
    )
    user = next(c for c in captured if "Hashtags must be invented" in c)
    assert "melted trophy waterfall" in user
    assert "participation trophy" in user
    assert "Smartly" in user or "adtech" in user
    assert "vanity metrics" in user


def test_clean_hashtags_keeps_valid_drops_banned_and_junk() -> None:
    tags = _clean_hashtags(
        ["AIAds", "#AIAds", "#Growth Marketing", "#marketing", "!!!", "#ok_tag"],
        "linkedin",
        5,
    )
    assert tags == ["#aiads", "#growthmarketing", "#ok_tag"]


def test_publish_caption_text_joins_hashtags() -> None:
    text = publish_caption_text(PublishVariation(caption="hook line", hashtags=["#a", "#b"]))
    assert text == "hook line\n\n#a #b"


def test_publish_caption_text_omits_empty_hashtags() -> None:
    text = publish_caption_text(PublishVariation(caption="hook only", hashtags=[]))
    assert text == "hook only"
