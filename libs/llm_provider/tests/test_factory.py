import pytest

from llm_provider.factory import get_llm_provider
from llm_provider.gemini import GeminiOpenAICompatProvider


def test_get_llm_provider_returns_gemini_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_provider.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    provider = get_llm_provider()

    assert isinstance(provider, GeminiOpenAICompatProvider)
    get_llm_provider.cache_clear()


def test_get_llm_provider_raises_on_unknown_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    get_llm_provider.cache_clear()
    monkeypatch.setenv("LLM_PROVIDER", "nonexistent")

    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        get_llm_provider()

    get_llm_provider.cache_clear()
