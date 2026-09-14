from app.creative import CreativeRequest, generate_creative
from httpx import AsyncClient

from tests.fakes import FakeLLMProvider


async def test_generate_comment_creative() -> None:
    provider = FakeLLMProvider(completion="love this angle — receipts > vibes.")
    result = await generate_creative(
        CreativeRequest(
            kind="comment",
            report_markdown="# Report\n## Themes\n- meme heat",
            brand_name="Pixis",
            voice_notes="witty",
            competitor_caption="we shipped v2",
        ),
        provider,
    )
    assert result.kind == "comment"
    assert "receipts" in result.text


async def test_generate_image_creative() -> None:
    provider = FakeLLMProvider(image_concept="neon split screen product")
    result = await generate_creative(
        CreativeRequest(
            kind="image",
            report_markdown="# Report\n## Gaps\n- founder POV missing",
            brand_name="Pixis",
        ),
        provider,
    )
    assert result.kind == "image"
    assert result.image_concept
    assert result.image_data_base64
    assert result.image_mime_type == "image/png"


async def test_meme_studio_sends_roast_pack() -> None:
    captured: list[object] = []

    class CaptureProvider(FakeLLMProvider):
        async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            captured.append(messages)
            return (
                '{"caption":"they post thrice a day and still mid",'
                '"overlay_text":"Cadence is a personality",'
                '"why_slaps":"rival cadence 2.1 vs brand 0.4",'
                '"hashtags":[],'
                '"image_brief":"sleep-deprived founder staring at empty calendar"}'
            )

    result = await generate_creative(
        CreativeRequest(
            kind="studio",
            format="meme",
            brand_name="Pixis",
            voice_notes="dry",
            brand_category="adtech",
            ideal_customer="growth marketers",
            content_pillars="receipts over vibes",
            preferred_formats=["meme", "hot_take"],
            facts_json='{"brand":{"name":"Pixis"},"rivals":[{"name":"Smartly","avgEngagement":140}]}',
        ),
        CaptureProvider(),
    )
    assert result.kind == "studio"
    assert captured
    user = captured[0][1].content  # type: ignore[index]
    assert "ROAST_PACK" in user
    assert "adtech" in user
    assert "growth marketers" in user
    assert "Smartly" in user


async def test_creative_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/creative/generate",
        json={
            "kind": "reply",
            "report_markdown": "# Discovery\n## Plays\n- reply with receipts",
            "brand_name": "Pixis",
            "voice_notes": "sharp",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "reply"
    assert body["text"] == "a generated caption"

