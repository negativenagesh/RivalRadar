from __future__ import annotations

from llm_provider.base import ImageResult, LLMProvider, LLMProviderError, Message


class RoutingLLMProvider:
    """Text from one vendor, pixels from Gemini, Agnes, or NVIDIA FLUX."""

    def __init__(self, text: LLMProvider, image: LLMProvider | None) -> None:
        self._text = text
        self._image = image

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        return await self._text.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        return await self._text.generate_image_concept(brief, style_hints=style_hints)

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        if self._image is None:
            raise LLMProviderError(
                "No image model. Paste Gemini for Nano Banana 2, or Agnes for Image 2.5 Flash. "
                "NVIDIA FLUX is a fallback. DeepSeek Flash cannot paint a PNG.",
                status_code=400,
            )
        return await self._image.generate_image(
            brief, style_hints=style_hints, aspect_ratio=aspect_ratio
        )
