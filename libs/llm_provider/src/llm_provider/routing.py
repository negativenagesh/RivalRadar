from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from llm_provider.base import ImageResult, LLMProvider, LLMProviderError, Message

logger = logging.getLogger("llm_provider.routing")


class RoutingLLMProvider:
    """Text from one vendor (with optional failover), pixels from Gemini, Agnes, or NVIDIA FLUX."""

    def __init__(
        self,
        text: LLMProvider,
        image: LLMProvider | None,
        *,
        text_fallbacks: list[LLMProvider] | None = None,
    ) -> None:
        self._text = text
        self._image = image
        self._text_fallbacks = list(text_fallbacks or [])
        # After a retriable primary failure, prefer fallbacks for the rest of this request.
        self._skip_primary = False

    def _text_chain(self) -> list[LLMProvider]:
        if self._skip_primary and self._text_fallbacks:
            return list(self._text_fallbacks)
        return [self._text, *self._text_fallbacks]

    @staticmethod
    def _retriable(exc: LLMProviderError) -> bool:
        return exc.status_code in {502, 503, 504}

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        last: LLMProviderError | None = None
        chain = self._text_chain()
        for idx, provider in enumerate(chain):
            try:
                return await provider.complete(
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    reasoning_effort=reasoning_effort,
                )
            except LLMProviderError as exc:
                last = exc
                if idx < len(chain) - 1 and self._retriable(exc):
                    if provider is self._text:
                        self._skip_primary = True
                    logger.warning(
                        "text provider failed (%s); trying fallback: %s",
                        exc.status_code,
                        exc.detail,
                    )
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
        # Streaming stays on the primary text model; failover is for non-stream complete().
        async for chunk in self._text.complete_stream(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        ):
            yield chunk

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        last: LLMProviderError | None = None
        chain = self._text_chain()
        for idx, provider in enumerate(chain):
            try:
                return await provider.generate_image_concept(brief, style_hints=style_hints)
            except LLMProviderError as exc:
                last = exc
                if idx < len(chain) - 1 and self._retriable(exc):
                    if provider is self._text:
                        self._skip_primary = True
                    logger.warning(
                        "text provider failed (%s); trying fallback: %s",
                        exc.status_code,
                        exc.detail,
                    )
                    continue
                raise
        assert last is not None
        raise last

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        if self._image is None:
            raise LLMProviderError(
                "No image model. Paste Gemini for Nano Banana 2, or Agnes for Image 2.0 Flash. "
                "NVIDIA FLUX is a fallback. DeepSeek Flash cannot paint a PNG.",
                status_code=400,
            )
        return await self._image.generate_image(
            brief, style_hints=style_hints, aspect_ratio=aspect_ratio
        )
