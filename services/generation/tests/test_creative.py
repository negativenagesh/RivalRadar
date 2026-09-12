from app.creative import CreativeRequest, generate_creative
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


async def test_creative_endpoint(client) -> None:
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
