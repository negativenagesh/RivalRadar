from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from llm_provider.base import LLMProviderError
from llm_provider.chat_util import message_text
from llm_provider.deepseek import DeepSeekProvider
from llm_provider.factory import provider_from_operator
from llm_provider.gemini import GeminiOpenAICompatProvider
from llm_provider.nvidia import NvidiaFluxProvider, NvidiaGptOssProvider
from llm_provider.routing import RoutingLLMProvider


def test_message_text_prefers_content_then_reasoning() -> None:
    assert message_text(SimpleNamespace(content="pong", reasoning_content="scratch")) == "pong"
    assert message_text(SimpleNamespace(content="", reasoning_content="  think  ")) == "think"


async def test_deepseek_complete_disables_thinking() -> None:
    provider = DeepSeekProvider("sk-test")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="pong", reasoning_content=None))]
        )
    )
    text = await provider.complete(
        [],
        temperature=0.3,
        max_tokens=200,
        reasoning_effort="low",
    )
    assert text == "pong"
    called = provider._client.chat.completions.create.await_args
    assert called is not None
    kwargs = called.kwargs
    assert kwargs["model"] == "deepseek-flash"
    assert kwargs["max_tokens"] >= 1024
    assert kwargs["extra_body"]["thinking"]["type"] == "disabled"


async def test_deepseek_generate_image_is_explicitly_unsupported() -> None:
    with pytest.raises(LLMProviderError, match="does not paint"):
        await DeepSeekProvider("sk-test").generate_image("a lime poster")


async def test_gptoss_uses_nvidia_card_settings() -> None:
    provider = NvidiaGptOssProvider("nv-test")
    provider._client.chat.completions.create = AsyncMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="9.11 is larger.", reasoning_content="compare")
                )
            ]
        )
    )
    text = await provider.complete([], temperature=1, max_tokens=16)
    assert "9.11" in text
    called = provider._client.chat.completions.create.await_args
    assert called is not None
    kwargs = called.kwargs
    assert kwargs["model"] == "openai/gpt-oss-20b"
    assert kwargs["max_tokens"] == 4096
    assert kwargs["top_p"] == 1
    assert kwargs["temperature"] == 1


async def test_flux_decodes_b64_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"data": [{"b64_json": "aGVsbG8="}]}

    class _Client:
        last_json: dict[str, object] | None = None

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(
            self,
            url: str,
            headers: dict[str, str] | None = None,
            json: dict[str, object] | None = None,
        ) -> _Resp:
            assert url.endswith("/images/generations")
            type(self).last_json = json
            return _Resp()

    monkeypatch.setattr("llm_provider.nvidia.httpx.AsyncClient", _Client)
    image = await NvidiaFluxProvider("nv-test").generate_image("lime poster", aspect_ratio="4:5")
    assert image.data == b"hello"
    assert _Client.last_json is not None
    assert _Client.last_json["model"] == "black-forest-labs/flux.1-schnell"
    assert _Client.last_json["size"] == "768x1024"


def test_operator_routes_gemini_text_and_forces_nano_banana() -> None:
    stack = provider_from_operator(
        gemini_key="AIza-test",
        nvidia_key="nv-test",
        text_model="gemini",
        image_model="nvidia_flux",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, GeminiOpenAICompatProvider)
    assert stack._image is stack._text


def test_operator_deepseek_text_gemini_image() -> None:
    stack = provider_from_operator(
        gemini_key="AIza-test",
        deepseek_key="sk-test",
        text_model="deepseek",
        image_model="nvidia_flux",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, DeepSeekProvider)
    assert isinstance(stack._image, GeminiOpenAICompatProvider)


def test_operator_gptoss_plus_flux_without_gemini() -> None:
    stack = provider_from_operator(
        nvidia_key="nv-test",
        text_model="gptoss",
        image_model="nvidia_flux",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, NvidiaGptOssProvider)
    assert isinstance(stack._image, NvidiaFluxProvider)


def test_operator_deepseek_only_has_no_image_backend() -> None:
    stack = provider_from_operator(deepseek_key="sk-test", text_model="deepseek", image_model="none")
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, DeepSeekProvider)
    assert stack._image is None
