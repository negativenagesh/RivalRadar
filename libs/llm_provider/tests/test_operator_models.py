from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from llm_provider.agnes import AgnesImageProvider
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


async def test_agnes_uses_exact_size_for_2_0_and_decodes_b64(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr("llm_provider.agnes.httpx.AsyncClient", _Client)
    image = await AgnesImageProvider("sk-agnes-test").generate_image(
        "lime hoodie", aspect_ratio="4:5"
    )
    assert image.data == b"hello"
    assert _Client.last_json is not None
    assert _Client.last_json["model"] == "agnes-image-2.0-flash"
    assert _Client.last_json["size"] == "864x1152"
    assert "ratio" not in _Client.last_json
    assert _Client.last_json["return_base64"] is True


async def test_agnes_2_5_still_uses_tier_size(monkeypatch: pytest.MonkeyPatch) -> None:
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
            type(self).last_json = json
            return _Resp()

    monkeypatch.setattr("llm_provider.agnes.httpx.AsyncClient", _Client)
    await AgnesImageProvider(
        "sk-agnes-test", model="agnes-image-2.5-flash"
    ).generate_image("hoodie", aspect_ratio="1:1")
    assert _Client.last_json is not None
    assert _Client.last_json["size"] == "1K"
    assert _Client.last_json["ratio"] == "1:1"

async def test_agnes_falls_back_to_image_url(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Gen:
        status_code = 200

        def json(self) -> dict[str, object]:
            return {"data": [{"url": "https://cdn.example/out.png", "b64_json": None}]}

    class _File:
        status_code = 200
        content = b"\x89PNG" + b"pixels"

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> _Gen:
            return _Gen()

        async def get(self, url: str) -> _File:
            assert url == "https://cdn.example/out.png"
            return _File()

    monkeypatch.setattr("llm_provider.agnes.httpx.AsyncClient", _Client)
    image = await AgnesImageProvider("sk-agnes-test").generate_image("hoodie")
    assert image.mime_type == "image/png"
    assert image.data.startswith(b"\x89PNG")


def test_operator_requested_image_wins_when_its_key_exists() -> None:
    stack = provider_from_operator(
        gemini_key="AIza-test",
        nvidia_key="nv-test",
        text_model="gemini",
        image_model="nvidia_flux",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, GeminiOpenAICompatProvider)
    assert isinstance(stack._image, NvidiaFluxProvider)


def test_operator_deepseek_text_gemini_image(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
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


def test_operator_deepseek_plus_agnes_without_gemini() -> None:
    stack = provider_from_operator(
        deepseek_key="sk-test",
        agnes_key="sk-agnes",
        text_model="deepseek",
        image_model="agnes",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, DeepSeekProvider)
    assert isinstance(stack._image, AgnesImageProvider)


def test_operator_agnes_pick_beats_gemini_default() -> None:
    stack = provider_from_operator(
        gemini_key="AIza-test",
        agnes_key="sk-agnes",
        text_model="gemini",
        image_model="agnes",
    )
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._image, AgnesImageProvider)


def test_operator_no_keys_falls_back_to_server_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-server")
    monkeypatch.setenv("AGNES_API_KEY", "agnes-server")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    stack = provider_from_operator()
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, NvidiaGptOssProvider)
    assert isinstance(stack._image, AgnesImageProvider)
    assert stack._text_fallbacks == []


def test_operator_gptoss_keeps_gemini_as_text_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    stack = provider_from_operator(
        nvidia_key="nv-op",
        gemini_key="AIza-op",
        agnes_key="sk-agnes",
        text_model="gptoss",
        image_model="agnes",
    )
    assert isinstance(stack._text, NvidiaGptOssProvider)
    assert len(stack._text_fallbacks) == 1
    assert isinstance(stack._text_fallbacks[0], GeminiOpenAICompatProvider)


async def test_routing_fails_over_on_timeout() -> None:
    primary = AsyncMock()
    primary.complete = AsyncMock(side_effect=LLMProviderError("timed out", status_code=504))
    backup = AsyncMock()
    backup.complete = AsyncMock(return_value="meme json")
    stack = RoutingLLMProvider(primary, None, text_fallbacks=[backup])
    assert await stack.complete([]) == "meme json"
    primary.complete.assert_awaited_once()
    backup.complete.assert_awaited_once()
    # Sticky: later completes skip the dead primary.
    backup.complete = AsyncMock(return_value="again")
    assert await stack.complete([]) == "again"
    assert primary.complete.await_count == 1
    backup.complete.assert_awaited_once()


def test_translate_transport_timeout() -> None:
    from llm_provider.chat_util import translate_transport_error

    err = translate_transport_error(TimeoutError("x"), vendor="NVIDIA gpt-oss-20b")
    assert err.status_code == 504
    assert "timed out" in err.detail.lower()


def test_operator_no_keys_no_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GEMINI_API_KEY", "DEEPSEEK_API_KEY", "NVIDIA_API_KEY", "AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValueError, match="Models chip"):
        provider_from_operator()


def test_operator_deepseek_only_has_no_image_backend() -> None:
    stack = provider_from_operator(deepseek_key="sk-test", text_model="deepseek", image_model="none")
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, DeepSeekProvider)
    assert stack._image is None
