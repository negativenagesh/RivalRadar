import pytest

from llm_provider.factory import get_llm_provider, provider_from_key, provider_from_operator
from llm_provider.gemini import GeminiOpenAICompatProvider
from llm_provider.nvidia import NvidiaGptOssProvider
from llm_provider.routing import RoutingLLMProvider


def test_get_llm_provider_defaults_to_gptoss(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_provider.cache_clear()
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-test")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    provider = get_llm_provider()

    assert isinstance(provider, NvidiaGptOssProvider)
    get_llm_provider.cache_clear()


def test_get_llm_provider_gemini_only_when_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_provider.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    provider = get_llm_provider()

    assert isinstance(provider, GeminiOpenAICompatProvider)
    get_llm_provider.cache_clear()


def test_get_llm_provider_raises_on_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_provider.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "nonexistent")

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()

    get_llm_provider.cache_clear()


def test_provider_from_key_is_uncached_and_rejects_blank() -> None:
    first = provider_from_key("operator-key-aaaa")
    second = provider_from_key("operator-key-bbbb")
    assert first is not second
    assert isinstance(first, GeminiOpenAICompatProvider)
    with pytest.raises(ValueError, match="required"):
        provider_from_key("  ")


def test_server_gemini_env_is_ignored_without_operator_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gm-server-should-not-be-used")
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-server")
    monkeypatch.setenv("AGNES_API_KEY", "agnes-server")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    stack = provider_from_operator(text_model="gptoss", image_model="agnes")
    assert isinstance(stack, RoutingLLMProvider)
    assert isinstance(stack._text, NvidiaGptOssProvider)
    assert stack._text_fallbacks == []
