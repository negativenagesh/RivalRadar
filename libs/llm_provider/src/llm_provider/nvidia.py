from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from openai import APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import ImageResult, LLMProviderError, Message
from llm_provider.chat_util import message_text, translate_vendor_error

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
# https://build.nvidia.com/openai/gpt-oss-20b/modelcard
DEFAULT_TEXT_MODEL = "openai/gpt-oss-20b"
# Hosted OpenAI-compat image gen on the same NIM base URL.
DEFAULT_IMAGE_MODEL = "black-forest-labs/flux.1-schnell"
DEFAULT_MAX_TOKENS = 4096


class NvidiaGptOssProvider:
    """NVIDIA NIM free endpoint for openai/gpt-oss-20b (text only)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_TEXT_MODEL,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=90.0)
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        del reasoning_effort
        # Card default is 4096 — reasoning is billed against max_tokens.
        budget = max(max_tokens, DEFAULT_MAX_TOKENS)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [{"role": m.role, "content": m.content} for m in messages],
                ),
                temperature=temperature,
                top_p=1,
                max_tokens=budget,
            )
        except APIStatusError as exc:
            raise translate_vendor_error(exc, vendor="NVIDIA gpt-oss-20b") from exc
        return message_text(response.choices[0].message)

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        del reasoning_effort
        from llm_provider.stream_util import stream_chat_deltas

        budget = max(max_tokens, DEFAULT_MAX_TOKENS)
        async for piece in stream_chat_deltas(
            self._client,
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=budget,
            vendor="NVIDIA gpt-oss-20b",
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
