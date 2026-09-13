from __future__ import annotations

import os
from functools import lru_cache

from llm_provider.base import LLMProvider
from llm_provider.gemini import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TEXT_MODEL,
    GeminiOpenAICompatProvider,
)


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Build the configured LLMProvider from environment variables.

    LLM_PROVIDER selects the backend (currently only "gemini"). Adding a new
    provider means adding a branch here and an adapter module -- call sites
    never change.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "gemini").lower()

    if provider_name == "gemini":
        api_key = os.environ["GEMINI_API_KEY"]
        return provider_from_key(api_key)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider_name}")


def provider_from_key(api_key: str) -> LLMProvider:
    """Uncached Gemini client from an operator-supplied key (never lru_cache this)."""
    key = (api_key or "").strip()
    if not key:
        raise ValueError("Gemini API key is required")
    base_url = os.environ.get(
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    model = os.environ.get("GEMINI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
    image_model = os.environ.get("GEMINI_IMAGE_MODEL", DEFAULT_IMAGE_MODEL)
    return GeminiOpenAICompatProvider(
        api_key=key, base_url=base_url, model=model, image_model=image_model
    )
