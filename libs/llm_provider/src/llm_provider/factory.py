from __future__ import annotations

import os
from functools import lru_cache

from llm_provider.agnes import DEFAULT_BASE_URL as AGNES_BASE
from llm_provider.agnes import DEFAULT_IMAGE_MODEL as AGNES_MODEL
from llm_provider.agnes import PING_PROMPT as AGNES_PING_PROMPT
from llm_provider.agnes import AgnesImageProvider
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
IMAGE_MODELS = frozenset({"nano_banana", "agnes", "nvidia_flux", "none"})

# Server-env Mission defaults: gpt-oss + Agnes only. Gemini / Nano Banana are
# operator-paste only — never pulled from GEMINI_API_KEY for failover/defaults.
TEXT_FALLBACK_ORDER = ("gptoss", "deepseek")
IMAGE_FALLBACK_ORDER = ("agnes", "nvidia_flux")

_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "gptoss": "NVIDIA_API_KEY",
    "nano_banana": "GEMINI_API_KEY",
    "agnes": "AGNES_API_KEY",
    "nvidia_flux": "NVIDIA_API_KEY",
}

_ENV_VENDOR = {
    "GEMINI_API_KEY": "gemini",
    "DEEPSEEK_API_KEY": "deepseek",
    "NVIDIA_API_KEY": "nvidia",
    "AGNES_API_KEY": "agnes",
}


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _model_key(model: str, keys: dict[str, str]) -> str:
    """Effective key for a model id from merged operator+env keys."""
    vendor = _ENV_VENDOR[_KEY_ENV[model]]
    return keys.get(vendor, "")


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    """Build the configured LLMProvider from environment variables.

    Default Mission/service backend is gpt-oss (NVIDIA). Gemini is only used
    when LLM_PROVIDER=gemini *and* GEMINI_API_KEY is set — not as an implicit
    fallback. Mission intel/studio use provider_from_operator instead.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "gptoss").lower()
    if provider_name in {"gptoss", "nvidia"}:
        return _gptoss(_need(_env("NVIDIA_API_KEY"), "NVIDIA"))
    if provider_name == "deepseek":
        return _deepseek(_need(_env("DEEPSEEK_API_KEY"), "DeepSeek"))
    if provider_name == "gemini":
        return provider_from_key(_need(_env("GEMINI_API_KEY"), "Gemini"))
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


def _agnes(key: str) -> AgnesImageProvider:
    return AgnesImageProvider(
        key,
        base_url=os.environ.get("AGNES_BASE_URL", AGNES_BASE),
        model=os.environ.get("AGNES_IMAGE_MODEL", AGNES_MODEL),
    )


def provider_from_operator(
    *,
    gemini_key: str | None = None,
    deepseek_key: str | None = None,
    nvidia_key: str | None = None,
    agnes_key: str | None = None,
    text_model: str | None = None,
    image_model: str | None = None,
) -> LLMProvider:
    """Uncached Mission stack: operator header keys win; server env for gpt-oss/Agnes only.

    Gemini / Nano Banana never read GEMINI_API_KEY from the server env — only an
    operator-pasted X-Gemini-Key enables them. Defaults: gpt-oss + Agnes.
    """
    operator_gemini = (gemini_key or "").strip()
    keys = {
        # Operator-only: never fall back to GEMINI_API_KEY from .env
        "gemini": operator_gemini,
        "deepseek": (deepseek_key or "").strip() or _env("DEEPSEEK_API_KEY"),
        "nvidia": (nvidia_key or "").strip() or _env("NVIDIA_API_KEY"),
        "agnes": (agnes_key or "").strip() or _env("AGNES_API_KEY"),
    }

    requested_text = (text_model or "").strip().lower() or _env("MISSION_TEXT_MODEL") or "gptoss"
    if requested_text not in TEXT_MODELS:
        raise ValueError("Text model must be gemini, deepseek, or gptoss.")
    # Gemini only enters the order when the operator pasted a key.
    text_order = [requested_text, *[m for m in TEXT_FALLBACK_ORDER if m != requested_text]]
    if operator_gemini and "gemini" not in text_order:
        text_order.append("gemini")
    text_id = next((m for m in text_order if _model_key(m, keys)), None)
    if text_id is None:
        raise ValueError(
            "Paste a key in the Models chip, or set NVIDIA_API_KEY / AGNES_API_KEY on the server."
        )
    if text_id == "gemini":
        text: LLMProvider = _gemini(keys["gemini"])
    elif text_id == "deepseek":
        text = _deepseek(keys["deepseek"])
    else:
        text = _gptoss(keys["nvidia"])

    text_fallbacks: list[LLMProvider] = []
    for mid in text_order:
        if mid == text_id or not _model_key(mid, keys):
            continue
        if mid == "gemini":
            text_fallbacks.append(_gemini(keys["gemini"]))
        elif mid == "deepseek":
            text_fallbacks.append(_deepseek(keys["deepseek"]))
        else:
            text_fallbacks.append(_gptoss(keys["nvidia"]))

    requested_image = (image_model or "").strip().lower() or _env("MISSION_IMAGE_MODEL") or "agnes"
    if requested_image not in IMAGE_MODELS:
        raise ValueError("Image model must be nano_banana, agnes, nvidia_flux, or none.")
    image: LLMProvider | None = None
    if requested_image != "none":
        image_order = [requested_image, *[m for m in IMAGE_FALLBACK_ORDER if m != requested_image]]
        # Nano Banana only when operator pasted Gemini — never from server env.
        if operator_gemini and "nano_banana" not in image_order:
            image_order.append("nano_banana")
        for image_id in image_order:
            if image_id == "nano_banana" and keys["gemini"]:
                image = text if text_id == "gemini" else _gemini(keys["gemini"])
                break
            if image_id == "agnes" and keys["agnes"]:
                image = _agnes(keys["agnes"])
                break
            if image_id == "nvidia_flux" and keys["nvidia"]:
                image = _flux(keys["nvidia"])
                break

    return RoutingLLMProvider(text, image, text_fallbacks=text_fallbacks)


def server_model_defaults() -> dict[str, object]:
    """Which Mission models the server can drive from env keys alone (no operator keys)."""
    text_id = next(
        (
            m
            for m in (
                _env("MISSION_TEXT_MODEL") or "gptoss",
                *TEXT_FALLBACK_ORDER,
            )
            if m != "gemini" and _env(_KEY_ENV[m])
        ),
        None,
    )
    image_id = next(
        (
            m
            for m in (
                _env("MISSION_IMAGE_MODEL") or "agnes",
                *IMAGE_FALLBACK_ORDER,
            )
            if m not in {"none", "nano_banana"} and _env(_KEY_ENV[m])
        ),
        None,
    )
    return {
        "text_model": text_id,
        "image_model": image_id,
        "available": text_id is not None,
        "source": "server-env",
    }


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
    elif kind == "agnes":
        painter = _agnes(key)
        image = await painter.generate_image(AGNES_PING_PROMPT, aspect_ratio="1:1")
        if not image.data:
            raise ValueError("Agnes painted an empty image. Try again.")
        preview = f"{image.mime_type} {len(image.data)} bytes"
        return {"vendor": kind, "model": AGNES_MODEL, "preview": preview}
    else:
        raise ValueError("Vendor must be gemini, deepseek, nvidia, or agnes.")
    text = await provider.complete(ping, temperature=0.0, max_tokens=32, reasoning_effort="low")
    preview = (text or "").replace("\n", " ").strip()[:80]
    if not preview:
        raise ValueError(f"{kind} answered empty. Try again or pick another model.")
    return {"vendor": kind, "model": model, "preview": preview}
