from __future__ import annotations

import asyncio
import base64
import logging
import os
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import ImageResult, LLMProviderError, Message
from llm_provider.chat_util import translate_transport_error, translate_vendor_error

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
# gpt-oss-20b on the free NIM often queues forever; mistral-nemotron answers on the same key.
DEFAULT_TEXT_MODEL = "mistralai/mistral-nemotron"
# Optional second try (override via NVIDIA_TEXT_FALLBACK_MODEL). Empty = no failover.
DEFAULT_FALLBACK_TEXT_MODEL = ""
# Hosted OpenAI-compat image gen on the same NIM base URL.
DEFAULT_IMAGE_MODEL = "black-forest-labs/flux.1-schnell"
# gpt-oss spends tokens on hidden reasoning — floor for short calls, full card default for intel-scale.
DEFAULT_MAX_TOKENS = 4096
STUDIO_MIN_TOKENS = 2048
_PRIMARY_TIMEOUT = 90.0
_FALLBACK_TIMEOUT = 60.0
_CLIENT_TIMEOUT = 100.0
_REASONING_EFFORTS = frozenset({"low", "medium", "high"})

logger = logging.getLogger("llm_provider.nvidia")


def _token_budget(max_tokens: int) -> int:
    """Reasoning eats the budget; don't force 4096 on every short Mission call."""
    if max_tokens >= 2000:
        return max(max_tokens, DEFAULT_MAX_TOKENS)
    return max(max_tokens, STUDIO_MIN_TOKENS)


def _effort(reasoning_effort: str | None) -> str:
    # NVIDIA defaults to medium when omitted — that hangs Mission studio captions.
    raw = (reasoning_effort or "low").strip().lower()
    return raw if raw in _REASONING_EFFORTS else "low"


def _fallback_model() -> str:
    return (
        os.environ.get("NVIDIA_TEXT_FALLBACK_MODEL", DEFAULT_FALLBACK_TEXT_MODEL).strip()
        or DEFAULT_FALLBACK_TEXT_MODEL
    )


def _is_gpt_oss(model: str) -> bool:
    return "gpt-oss" in model.lower()


def _vendor(model: str) -> str:
    short = model.split("/")[-1] if "/" in model else model
    return f"NVIDIA {short}"


class NvidiaGptOssProvider:
    """NVIDIA NIM text — prefers gpt-oss-20b, fails over to mistral-nemotron on hang."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_TEXT_MODEL,
        fallback_model: str | None = None,
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(_CLIENT_TIMEOUT, connect=15.0),
        )
        self._model = model
        fb = (fallback_model if fallback_model is not None else _fallback_model()).strip()
        self._fallback_model = fb if fb and fb != model else ""
        # Sticky: once gpt-oss hangs, prefer the fallback for this provider instance.
        self._prefer_fallback = False

    def _model_chain(self) -> list[tuple[str, float]]:
        if self._prefer_fallback and self._fallback_model:
            return [(self._fallback_model, _FALLBACK_TIMEOUT)]
        chain = [(self._model, _PRIMARY_TIMEOUT)]
        if self._fallback_model:
            chain.append((self._fallback_model, _FALLBACK_TIMEOUT))
        return chain

    async def _stream_complete(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float,
        budget: int,
        reasoning_effort: str | None,
        timeout: float,
    ) -> str:
        vendor = _vendor(model)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": cast(
                list[ChatCompletionMessageParam],
                [{"role": m.role, "content": m.content} for m in messages],
            ),
            "temperature": temperature,
            "max_tokens": budget,
            "stream": True,
        }
        # gpt-oss card uses top_p=1; forcing it on mistral-nemotron stalls generation.
        if _is_gpt_oss(model):
            kwargs["top_p"] = 1
            kwargs["extra_body"] = {"reasoning_effort": _effort(reasoning_effort)}

        async def _consume() -> str:
            stream = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream:
                choices = getattr(chunk, "choices", None) or []
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                if delta is None:
                    continue
                piece = getattr(delta, "content", None)
                if isinstance(piece, str) and piece:
                    content_parts.append(piece)
                    continue
                reasoning = getattr(delta, "reasoning_content", None)
                if isinstance(reasoning, str) and reasoning:
                    reasoning_parts.append(reasoning)
            text = "".join(content_parts).strip() or "".join(reasoning_parts).strip()
            if not text:
                raise LLMProviderError(
                    f"{vendor} returned empty text. Try Generate again.",
                    status_code=502,
                )
            return text

        try:
            return await asyncio.wait_for(_consume(), timeout=timeout)
        except TimeoutError as exc:
            raise translate_transport_error(exc, vendor=vendor) from exc
        except APIStatusError as exc:
            raise translate_vendor_error(exc, vendor=vendor) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise translate_transport_error(exc, vendor=vendor) from exc

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        budget = _token_budget(max_tokens)
        last: LLMProviderError | None = None
        chain = self._model_chain()
        for idx, (model, timeout) in enumerate(chain):
            try:
                text = await self._stream_complete(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    budget=_token_budget(max_tokens) if _is_gpt_oss(model) else max(max_tokens, 512),
                    reasoning_effort=reasoning_effort,
                    timeout=timeout,
                )
                if model != self._model:
                    self._prefer_fallback = True
                return text
            except LLMProviderError as exc:
                last = exc
                if idx < len(chain) - 1 and exc.status_code in {502, 503, 504}:
                    logger.warning(
                        "NVIDIA primary text timed out/failed (%s); failing over to %s",
                        exc.detail,
                        chain[idx + 1][0],
                    )
                    if model == self._model:
                        self._prefer_fallback = True
                    continue
                raise
        assert last is not None
        raise last

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        from llm_provider.stream_util import stream_chat_deltas

        model = self._fallback_model if self._prefer_fallback and self._fallback_model else self._model
        budget = _token_budget(max_tokens) if _is_gpt_oss(model) else max(max_tokens, 1024)
        extra = {"reasoning_effort": _effort(reasoning_effort)} if _is_gpt_oss(model) else None
        async for piece in stream_chat_deltas(
            self._client,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=budget,
            vendor=_vendor(model),
            extra_body=extra,
            include_reasoning=False,
        ):
            yield piece

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        hints = ", ".join(style_hints) if style_hints else "none"
        return await self.complete(
            [
                Message(
                    role="user",
                    content=(
                        "Write one detailed visual concept (composition, subject, mood, palette). "
                        f"Style hints: {hints}.\n\n{brief}"
                    ),
                )
            ],
            temperature=0.8,
            max_tokens=512,
        )

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        raise LLMProviderError(
            "gpt-oss-20b is text-only. Pick Agnes Image 2.0 Flash or NVIDIA FLUX, or paste Gemini for Nano Banana 2.",
            status_code=400,
        )


class NvidiaFluxProvider:
    """NVIDIA NIM OpenAI-compat /images/generations (FLUX) for operator image fallback."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_IMAGE_MODEL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        del messages, temperature, max_tokens, reasoning_effort
        raise LLMProviderError("FLUX is an image model. Pick gpt-oss-20b for text.", status_code=400)

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        del messages, temperature, max_tokens, reasoning_effort
        raise LLMProviderError("FLUX is an image model. Pick gpt-oss-20b for text.", status_code=400)
        yield ""  # pragma: no cover

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        del brief, style_hints
        raise LLMProviderError("FLUX does not write captions.", status_code=400)

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        hints = ", ".join(style_hints) if style_hints else "none"
        prompt = f"{brief}\nStyle: {hints}."
        size = {
            "1:1": "1024x1024",
            "4:5": "768x1024",
            "16:9": "1280x768",
            "9:16": "768x1280",
        }.get(aspect_ratio or "1:1", "1024x1024")
        url = f"{self._base_url}/images/generations"
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt[:4000],
            "n": 1,
            "response_format": "b64_json",
            "size": size,
        }
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"NVIDIA FLUX unreachable ({exc.__class__.__name__})",
                status_code=502,
            ) from exc
        if response.status_code >= 400:
            message = response.text[:800]
            try:
                err = response.json()
                if isinstance(err, dict):
                    blob = err.get("error") or err
                    if isinstance(blob, dict):
                        message = str(blob.get("message") or message)
            except Exception:  # noqa: BLE001
                pass
            class _Err(Exception):
                def __init__(self) -> None:
                    super().__init__(message)
                    self.status_code = response.status_code

            raise translate_vendor_error(_Err(), vendor="NVIDIA FLUX")
        try:
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError("NVIDIA FLUX returned a non-JSON body", status_code=502) from exc
        rows = body.get("data") if isinstance(body, dict) else None
        if not isinstance(rows, list) or not rows:
            raise LLMProviderError("NVIDIA FLUX returned no image bytes. Try Generate again.", status_code=502)
        first = rows[0] if isinstance(rows[0], dict) else {}
        b64 = first.get("b64_json") or first.get("b64")
        if not isinstance(b64, str) or not b64:
            raise LLMProviderError("NVIDIA FLUX returned no image bytes. Try Generate again.", status_code=502)
        return ImageResult(mime_type="image/png", data=base64.b64decode(b64))
