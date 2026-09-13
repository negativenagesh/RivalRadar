from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class LLMProviderError(Exception):
    """Vendor/API failure translated for HTTP handlers (never leak raw SDK traces)."""

    def __init__(self, detail: str, *, status_code: int = 502, retry_after: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code
        self.retry_after = retry_after


class Message(BaseModel):
    role: str
    content: str


class ImageResult(BaseModel):
    mime_type: str
    data: bytes


class LLMProvider(Protocol):
    """Adapter interface every model backend must implement.

    Business logic in generation/compliance depends only on this protocol,
    never on a vendor SDK, so the backing provider can be swapped via
    LLM_PROVIDER without touching call sites.
    """

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        """Return a single text completion for the given chat messages.

        `reasoning_effort` (e.g. "low" | "medium" | "high", provider-specific)
        is a hint for reasoning-capable models: hidden "thinking" tokens count
        against `max_tokens` on some providers (Gemini's OpenAI-compat
        endpoint included), so a low-latency classification task should pass
        "low" rather than silently risking a truncated response. Providers
        that don't support the concept ignore it.
        """
        ...

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        """Return a detailed text description of an image to be created.

        A cheap text-only preview step -- useful for showing a concept
        before committing to a paid generate_image call. Kept alongside
        generate_image, which returns real pixels.
        """
        ...

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        """Return actual generated image bytes for the given brief."""
        ...
