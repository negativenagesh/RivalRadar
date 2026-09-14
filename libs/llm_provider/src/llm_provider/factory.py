from __future__ import annotations

import os
from functools import lru_cache

from llm_provider.base import LLMProvider, Message
from llm_provider.deepseek import DEFAULT_BASE_URL as DEEPSEEK_BASE
from llm_provider.deepseek import DEFAULT_MODEL as DEEPSEEK_MODEL
from llm_provider.deepseek import DeepSeekProvider
from llm_provider.gemini import (
    DEFAULT_IMAGE_MODEL,
    DEFAULT_TEXT_MODEL,
    GeminiOpenAICompatProvider,
)
from llm_provider.nvidia import DEFAULT_BASE_URL as NVIDIA_BASE
from llm_provider.nvidia import DEFAULT_IMAGE_MODEL as NVIDIA_IMAGE_MODEL
from llm_provider.nvidia import DEFAULT_TEXT_MODEL as NVIDIA_TEXT_MODEL
from llm_provider.nvidia import NvidiaFluxProvider, NvidiaGptOssProvider
from llm_provider.routing import RoutingLLMProvider

TEXT_MODELS = frozenset({"gemini", "deepseek", "gptoss"})
IMAGE_MODELS = frozenset({"nano_banana", "nvidia_flux", "none"})


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Build the configured LLMProvider from environment variables.

    LLM_PROVIDER selects the backend (currently only "gemini"). Adding a new
    provider means adding a branch here and an adapter module -- call sites
    never change. Mission intel/studio use provider_from_operator instead.
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


def _need(key: str | None, label: str) -> str:
    value = (key or "").strip()
    if not value:
        raise ValueError(f"Paste your {label} API key in the Models chip.")
    return value


def _gemini(key: str) -> GeminiOpenAICompatProvider:
    provider = provider_from_key(key)
    assert isinstance(provider, GeminiOpenAICompatProvider)
    return provider


def _deepseek(key: str) -> DeepSeekProvider:
    return DeepSeekProvider(
        key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE),
        model=os.environ.get("DEEPSEEK_TEXT_MODEL", DEEPSEEK_MODEL),
    )


def _gptoss(key: str) -> NvidiaGptOssProvider:
    return NvidiaGptOssProvider(
        key,
        base_url=os.environ.get("NVIDIA_BASE_URL", NVIDIA_BASE),
        model=os.environ.get("NVIDIA_TEXT_MODEL", NVIDIA_TEXT_MODEL),
    )


def _flux(key: str) -> NvidiaFluxProvider:
    return NvidiaFluxProvider(
        key,
        base_url=os.environ.get("NVIDIA_BASE_URL", NVIDIA_BASE),
        model=os.environ.get("NVIDIA_IMAGE_MODEL", NVIDIA_IMAGE_MODEL),
    )


def provider_from_operator(
    *,
    gemini_key: str | None = None,
    deepseek_key: str | None = None,
    nvidia_key: str | None = None,
    text_model: str | None = None,
    image_model: str | None = None,
) -> LLMProvider:
    """Uncached Mission stack: text vendor + image vendor from operator headers."""
    text_id = (text_model or "gemini").strip().lower()
    if text_id not in TEXT_MODELS:
        raise ValueError("Text model must be gemini, deepseek, or gptoss.")
    image_id = (image_model or "").strip().lower() or (
        "nano_banana" if (gemini_key or "").strip() else "none"
    )
    if image_id not in IMAGE_MODELS:
        raise ValueError("Image model must be nano_banana, nvidia_flux, or none.")

    if text_id == "gemini":
        text: LLMProvider = _gemini(_need(gemini_key, "Gemini"))
    elif text_id == "deepseek":
        text = _deepseek(_need(deepseek_key, "DeepSeek"))
    else:
        text = _gptoss(_need(nvidia_key, "NVIDIA"))

    # Gemini key present → Nano Banana only (operator asked: use Gemini for pixels).
    image: LLMProvider | None
    gemini = (gemini_key or "").strip()
    if gemini:
        image = text if text_id == "gemini" else _gemini(gemini)
    elif image_id == "nvidia_flux":
        image = _flux(_need(nvidia_key, "NVIDIA"))
    else:
        image = None

    return RoutingLLMProvider(text, image)


async def ping_vendor(vendor: str, api_key: str) -> dict[str, str]:
    """Tiny live round-trip so the Models chip can reject a dead key before save."""
    kind = (vendor or "").strip().lower()
    key = _need(api_key, kind or "vendor")
    ping = [Message(role="user", content="Reply with exactly: pong")]
    if kind == "gemini":
        provider: LLMProvider = _gemini(key)
        model = DEFAULT_TEXT_MODEL
    elif kind == "deepseek":
        provider = _deepseek(key)
        model = DEEPSEEK_MODEL
    elif kind == "nvidia":
        provider = _gptoss(key)
        model = NVIDIA_TEXT_MODEL
    else:
        raise ValueError("Vendor must be gemini, deepseek, or nvidia.")
    text = await provider.complete(ping, temperature=0.0, max_tokens=32, reasoning_effort="low")
    preview = (text or "").replace("\n", " ").strip()[:80]
    if not preview:
        raise ValueError(f"{kind} answered empty. Try again or pick another model.")
    return {"vendor": kind, "model": model, "preview": preview}
