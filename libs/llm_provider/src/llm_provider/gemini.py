from __future__ import annotations

from typing import cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import Message

DEFAULT_TEXT_MODEL = "gemini-3.6-flash"


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
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        extra_body = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
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
