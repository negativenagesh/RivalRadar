from __future__ import annotations

import base64
import re
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import ImageResult, LLMProviderError, Message
from llm_provider.chat_util import translate_transport_error

DEFAULT_TEXT_MODEL = "gemini-3.6-flash"
# Nano Banana 2 — https://ai.google.dev/gemini-api/docs/image-generation
# Chat completions are not supported for this model; use generateContent.
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"

_RETRY_IN = re.compile(r"retry in ([\d.]+)\s*s", re.I)


def native_gemini_root(openai_compat_base: str) -> str:
    """Strip the OpenAI-compat suffix. Image models use generateContent, not chat.completions."""
    url = (openai_compat_base or "").strip().rstrip("/")
    if url.endswith("/openai"):
        url = url[: -len("/openai")]
    return url or "https://generativelanguage.googleapis.com/v1beta"


def translate_openai_error(exc: BaseException, *, kind: str = "text") -> LLMProviderError:
    status = int(getattr(exc, "status_code", 0) or 0)
    raw = str(exc)
    retry_after: int | None = None
    match = _RETRY_IN.search(raw)
    if match:
        retry_after = max(1, int(float(match.group(1))))
    if status == 429:
        wait = (
            f" Wait ~{retry_after}s and Generate again."
            if retry_after
            else " Wait a minute and Generate again."
        )
        compact = raw.lower().replace(" ", "")
        if kind == "image":
            if "limit:0" in compact or "limit: 0" in raw.lower():
                return LLMProviderError(
                    "This Gemini key has no Nano Banana 2 image quota. "
                    "Enable billing in Google AI Studio, then Generate again.",
                    status_code=429,
                    retry_after=retry_after,
                )
            return LLMProviderError(
                "Nano Banana 2 rate limit." + wait,
                status_code=429,
                retry_after=retry_after,
            )
        return LLMProviderError(
            "Gemini rate limit — free tier allows 5 text requests/minute on this model." + wait,
            status_code=429,
            retry_after=retry_after,
        )
    if status in {401, 403}:
        return LLMProviderError(
            "Gemini rejected this API key. Re-paste it in the navbar chip.",
            status_code=401,
        )
    if status == 400:
        return LLMProviderError(f"Gemini request failed: {raw[:240]}", status_code=400)
    return LLMProviderError("Gemini request failed. Try Generate again.", status_code=502)


def translate_status(status: int, message: str, *, kind: str = "text") -> LLMProviderError:
    class _Err(Exception):
        def __init__(self) -> None:
            super().__init__(message)
            self.status_code = status

    return translate_openai_error(_Err(), kind=kind)


def _inline_image(part: dict[str, Any]) -> tuple[str, bytes] | None:
    blob = part.get("inlineData") or part.get("inline_data")
    if not isinstance(blob, dict):
        return None
    data = blob.get("data")
    if not isinstance(data, str) or not data:
        return None
    mime = str(blob.get("mimeType") or blob.get("mime_type") or "image/png")
    return mime, base64.b64decode(data)


class GeminiOpenAICompatProvider:
    """Gemini adapter: text via OpenAI-compat chat.completions, images via native generateContent.

    Nano Banana 2 (`gemini-3.1-flash-image`) does not support chat completions.
    See ai.google.dev/gemini-api/docs/image-generation.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        model: str = DEFAULT_TEXT_MODEL,
        image_model: str = DEFAULT_IMAGE_MODEL,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=90.0)
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._image_model = image_model

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        extra_body = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [{"role": m.role, "content": m.content} for m in messages],
                ),
                temperature=temperature,
                max_tokens=max_tokens,
                extra_body=extra_body,
            )
        except APIStatusError as exc:
            raise translate_openai_error(exc) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise translate_transport_error(exc, vendor="Gemini") from exc
        return response.choices[0].message.content or ""

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        from llm_provider.stream_util import stream_chat_deltas

        extra_body = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        async for piece in stream_chat_deltas(
            self._client,
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            vendor="Gemini",
            extra_body=extra_body or None,
        ):
            yield piece

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        hints = ", ".join(style_hints) if style_hints else "none"
        prompt = (
            "You are a creative director writing an image brief for a designer. "
            "Given the following content brief, write a single detailed visual "
            "concept description (composition, subject, mood, color palette, "
            "typography if any) that a designer or an image-generation model "
            f"could execute directly. Style hints to honor: {hints}.\n\n"
            f"Content brief:\n{brief}"
        )
        return await self.complete(
            [Message(role="user", content=prompt)],
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
        """Nano Banana 2 via POST .../models/{id}:generateContent."""
        hints = ", ".join(style_hints) if style_hints else "none"
        prompt = (
            "Generate a single image for the following content brief. "
            f"Style hints to honor: {hints}.\n\nContent brief:\n{brief}"
        )
        root = native_gemini_root(self._base_url)
        url = f"{root}/models/{self._image_model}:generateContent"
        image_config: dict[str, str] = {"imageSize": "1K"}
        if aspect_ratio:
            image_config["aspectRatio"] = aspect_ratio
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": image_config,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "x-goog-api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Nano Banana unreachable ({exc.__class__.__name__})",
                status_code=502,
            ) from exc
        if response.status_code >= 400:
            message = response.text[:800]
            try:
                err = response.json().get("error") or {}
                if isinstance(err, dict):
                    message = str(err.get("message") or message)
            except Exception:  # noqa: BLE001
                pass
            raise translate_status(response.status_code, message, kind="image")
        try:
            body = response.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError("Nano Banana returned a non-JSON body", status_code=502) from exc
        if not isinstance(body, dict):
            raise LLMProviderError("Nano Banana returned an unexpected body", status_code=502)
        for candidate in body.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content") or {}
            if not isinstance(content, dict):
                continue
            for part in content.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                inline = _inline_image(part)
                if inline:
                    mime, data = inline
                    return ImageResult(mime_type=mime, data=data)
        raise LLMProviderError(
            f"Nano Banana 2 ({self._image_model}) returned no image bytes. Try Generate again.",
            status_code=502,
        )
