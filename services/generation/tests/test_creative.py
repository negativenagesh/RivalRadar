from app.creative import CreativeRequest, _looks_like_metric_overlay, generate_creative
from httpx import AsyncClient

from tests.fakes import FakeLLMProvider


def test_metric_overlay_detector() -> None:
    assert _looks_like_metric_overlay("Smartly: 18 Likes")
    assert _looks_like_metric_overlay("0 Comments. Pixis: Real Action")
    assert not _looks_like_metric_overlay("Crickets booked the venue")
    assert not _looks_like_metric_overlay("Their launch RSVP'd alone")


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


async def test_generate_image_creative_skips_text_llm() -> None:
    class Capture(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self.complete_calls = 0
            self.image_briefs: list[str] = []

        async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            self.complete_calls += 1
            return await super().complete(messages, **kwargs)

        async def generate_image(self, brief, **kwargs):  # type: ignore[no-untyped-def]
            self.image_briefs.append(brief)
            return await super().generate_image(brief, **kwargs)

    provider = Capture()
    result = await generate_creative(
        CreativeRequest(
            kind="image",
            report_markdown="# Report\n## Gaps\n- founder POV missing",
            brand_name="Pixis",
        ),
        provider,
    )
    assert result.kind == "image"
    assert provider.complete_calls == 0
    assert result.image_data_base64
    assert result.image_mime_type == "image/png"


async def test_studio_fast_mode_skips_text_llm() -> None:
    class Capture(FakeLLMProvider):
        def __init__(self) -> None:
            super().__init__()
            self.complete_calls = 0

        async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
            self.complete_calls += 1
            raise AssertionError("fast mode must not call text complete()")

    provider = Capture()
    result = await generate_creative(
        CreativeRequest(
            kind="studio",
            format="linkedin_thought",
            platform="linkedin",
            brand_name="Pixis",
            studio_mode="fast",
        ),
        provider,
    )
    assert result.kind == "studio"
    assert provider.complete_calls == 0
    assert result.generation_path == "fast_agnes"
    assert result.image_data_base64


async def test_studio_full_mode_calls_text_then_paints() -> None:
    provider = FakeLLMProvider(
        completion=(
            '{"caption":"AI without an explanation is a vibe, not a product.",'
            '"overlay_text":"Still true.",'
            '"why_slaps":"category fog",'
            '"hashtags":["build"],'
            '"image_brief":"lime editorial still"}'
        )
    )
    result = await generate_creative(
        CreativeRequest(
            kind="studio",
            format="linkedin_thought",
            platform="linkedin",
            brand_name="Pixis",
            studio_mode="full",
        ),
        provider,
    )
    assert result.kind == "studio"
    assert provider.complete_calls >= 1
    assert result.generation_path == "full_llm_agnes"
    assert "vibe" in result.text.lower() or "product" in result.text.lower()
    assert result.overlay_text == "Still true."
    assert result.image_data_base64


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

