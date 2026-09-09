from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class Message(BaseModel):
    role: str
    content: str


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
    ) -> str:
        """Return a single text completion for the given chat messages."""
        ...

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        """Return a detailed text description of an image to be created.

        v1 returns a structured text prompt (no pixels generated). The
        signature is deliberately image-model-shaped so a future
        `generate_image(...) -> bytes` adapter method is a drop-in
        extension rather than a redesign.
        """
        ...
