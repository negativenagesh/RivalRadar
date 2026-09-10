import base64

from app.drafting import draft_response
from app.schemas import DraftRequest
from app.voice.retrieval import load_corpus

from tests.fakes import FakeLLMProvider


async def test_draft_response_returns_caption_and_image_concept() -> None:
    corpus = load_corpus()
    provider = FakeLLMProvider(completion="on-brand caption", image_concept="a warm photo concept")
    request = DraftRequest(
        cluster_format="founder_post",
        cluster_theme="sustainability",
        competitor_caption="we care about the planet",
    )

    result = await draft_response(request, corpus, provider)

    assert result.caption == "on-brand caption"
    assert result.image_concept == "a warm photo concept"
    assert len(result.voice_examples_used) == 3


async def test_draft_response_strips_surrounding_quotes_from_caption() -> None:
    corpus = load_corpus()
    provider = FakeLLMProvider(completion='"a quoted caption"')
    request = DraftRequest(
        cluster_format="meme", cluster_theme="monday-mood", competitor_caption="mondays, am I right"
    )

    result = await draft_response(request, corpus, provider)

    assert result.caption == "a quoted caption"


async def test_draft_response_passes_theme_matched_examples_to_provider() -> None:
    corpus = load_corpus()
    provider = FakeLLMProvider()
    request = DraftRequest(
        cluster_format="product_launch_carousel",
        cluster_theme="sustainability",
        competitor_caption="new eco line",
    )

    result = await draft_response(request, corpus, provider)

    assert "halo-001" in result.voice_examples_used or "halo-002" in result.voice_examples_used
    assert provider.last_messages is not None


async def test_draft_response_includes_generated_image_bytes() -> None:
    corpus = load_corpus()
    provider = FakeLLMProvider(image_bytes=b"pngdata", image_mime_type="image/png")
    request = DraftRequest(
        cluster_format="meme", cluster_theme="monday-mood", competitor_caption="mondays, am I right"
    )

    result = await draft_response(request, corpus, provider)

    assert result.image_mime_type == "image/png"
    assert result.image_data_base64 == base64.b64encode(b"pngdata").decode("ascii")


async def test_draft_response_falls_back_gracefully_when_image_generation_fails() -> None:
    corpus = load_corpus()
    provider = FakeLLMProvider(raise_on_generate_image=True)
    request = DraftRequest(
        cluster_format="meme", cluster_theme="monday-mood", competitor_caption="mondays, am I right"
    )

    result = await draft_response(request, corpus, provider)

    assert result.image_mime_type is None
    assert result.image_data_base64 is None
    assert result.image_concept
