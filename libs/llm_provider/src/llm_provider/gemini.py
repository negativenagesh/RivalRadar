from __future__ import annotations

import base64
import re
from typing import Any, cast

from openai import APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import ImageResult, LLMProviderError, Message

DEFAULT_TEXT_MODEL = "gemini-3.6-flash"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-image"

_RETRY_IN = re.compile(r"retry in ([\d.]+)\s*s", re.I)


def translate_openai_error(exc: BaseException) -> LLMProviderError:
    status = int(getattr(exc, "status_code", 0) or 0)
    raw = str(exc)
    retry_after: int | None = None
    match = _RETRY_IN.search(raw)
    if match:
        retry_after = max(1, int(float(match.group(1))))
    if status == 429:
        wait = f" Wait ~{retry_after}s and Generate again." if retry_after else " Wait a minute and Generate again."
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


class GeminiOpenAICompatProvider:
    """LLMProvider backed by Gemini's OpenAI-compatible /chat/completions API.

    Uses the stock `openai` SDK pointed at Google's compat base URL, so no
    google-genai dependency is needed. See ai.google.dev/gemini-api/docs/openai.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        model: str = DEFAULT_TEXT_MODEL,
        image_model: str = DEFAULT_IMAGE_MODEL,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
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
        return response.choices[0].message.content or ""

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
    ) -> ImageResult:
        hints = ", ".join(style_hints) if style_hints else "none"
        prompt = (
            "Generate a single image for the following content brief. "
            f"Style hints to honor: {hints}.\n\nContent brief:\n{brief}"
        )
        try:
            response = await self._client.chat.completions.create(
                model=self._image_model,
                messages=[{"role": "user", "content": prompt}],
                extra_body={"modalities": ["image", "text"]},
            )
        except APIStatusError as exc:
            raise translate_openai_error(exc) from exc
        message: Any = response.choices[0].message
        images = getattr(message, "images", None) or []
        if not images:
            raise ValueError(
                f"Gemini image model '{self._image_model}' returned no image data"
            )
        image_url: str = images[0]["image_url"]["url"]
        mime_type, _, encoded = image_url.removeprefix("data:").partition(";base64,")
        return ImageResult(mime_type=mime_type, data=base64.b64decode(encoded))
