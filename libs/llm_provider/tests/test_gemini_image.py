import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from llm_provider.gemini import GeminiOpenAICompatProvider


def _fake_image_response(data_uri: str) -> SimpleNamespace:
    message = SimpleNamespace(images=[{"image_url": {"url": data_uri}}])
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


async def test_generate_image_decodes_base64_payload() -> None:
    provider = GeminiOpenAICompatProvider(api_key="k", base_url="https://example.test")
    raw_bytes = b"fake-png-bytes"
    data_uri = f"data:image/png;base64,{base64.b64encode(raw_bytes).decode()}"
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=_fake_image_response(data_uri)
    )

    result = await provider.generate_image("a meme about mondays", style_hints=["bold", "gen-z"])

    assert result.mime_type == "image/png"
    assert result.data == raw_bytes


async def test_generate_image_raises_when_no_image_returned() -> None:
    provider = GeminiOpenAICompatProvider(api_key="k", base_url="https://example.test")
    empty_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(images=None))])
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=empty_response
    )

    with pytest.raises(ValueError, match="returned no image data"):
        await provider.generate_image("a brief")
