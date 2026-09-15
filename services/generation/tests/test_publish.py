import json

from app.publish import (
    PublishPlanRequest,
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
    }
    base.update(overrides)
    return PublishPlanRequest(**base)  # type: ignore[arg-type]


async def test_publish_plan_parses_variations() -> None:
    payload = {
        "variations": [
            {
                "caption": "Your rival's dashboard is a meme. Yours isn't.",
                "hashtags": ["Marketing", "#Growth ", "#growth", "bad tag!!" * 20],
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
    assert "#marketing" in tags and "#growth" in tags
    assert len(tags) == len(set(tags))  # deduped
    assert all(" " not in t for t in tags)


async def test_publish_plan_fallback_when_llm_junk() -> None:
    fake = FakeLLMProvider(completion="not json at all")
    plan = await generate_publish_plan(_request(platform="instagram"), fake)
    assert len(plan.variations) == 1
    assert plan.variations[0].caption
    assert plan.variations[0].hashtags  # platform filler staples


async def test_publish_plan_caps_caption_length() -> None:
    payload = {"variations": [{"caption": "x" * 900, "hashtags": ["#one", "#two", "#three"], "why": ""}]}
    fake = FakeLLMProvider(completion=json.dumps(payload))
    plan = await generate_publish_plan(_request(platform="x"), fake)
    assert len(plan.variations[0].caption) <= 270
    assert len(plan.variations[0].hashtags) <= 2


def test_clean_hashtags_normalizes_and_limits() -> None:
    tags = _clean_hashtags(["AI", "#AI", "#Growth Marketing"], "linkedin", 5)
    assert tags == ["#ai", "#growthmarketing"]


def test_publish_caption_text_joins_hashtags() -> None:
    from app.publish import PublishVariation

    text = publish_caption_text(PublishVariation(caption="hook line", hashtags=["#a", "#b"]))
    assert text == "hook line\n\n#a #b"
