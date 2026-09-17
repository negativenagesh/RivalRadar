from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from openai import APIStatusError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import ImageResult, LLMProviderError, Message
from llm_provider.chat_util import message_text, translate_vendor_error

DEFAULT_BASE_URL = "https://api.deepseek.com"
# DeepSeek-V4.1-Flash — https://api-docs.deepseek.com/
DEFAULT_MODEL = "deepseek-flash"


class DeepSeekProvider:
    """OpenAI-compat chat for DeepSeek-V4.1-Flash (`deepseek-flash`).

    Native vision is image-in / text-out. It does not emit PNG bytes.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
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
        # Thinking tokens eat the output budget. Mission JSON needs the answer, not the scratchpad.
        thinking: dict[str, str] = {"type": "disabled"}
        extra: dict[str, object] = {"thinking": thinking}
        if reasoning_effort == "high":
            extra = {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
        budget = max(max_tokens, 1024)
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=cast(
                    list[ChatCompletionMessageParam],
                    [{"role": m.role, "content": m.content} for m in messages],
                ),
                temperature=temperature,
                max_tokens=budget,
                extra_body=extra,
            )
        except APIStatusError as exc:
            raise translate_vendor_error(exc, vendor="DeepSeek") from exc
        return message_text(response.choices[0].message)

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        from llm_provider.stream_util import stream_chat_deltas

        thinking: dict[str, str] = {"type": "disabled"}
        extra: dict[str, object] = {"thinking": thinking}
        if reasoning_effort == "high":
            extra = {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
        budget = max(max_tokens, 1024)
        async for piece in stream_chat_deltas(
            self._client,
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=budget,
            vendor="DeepSeek",
            extra_body=extra,
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
            reasoning_effort="low",
        )

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        raise LLMProviderError(
            "DeepSeek-V4.1-Flash understands images; it does not paint them. "
            "Paste Gemini for Nano Banana 2, Agnes for Image 2.0 Flash, or NVIDIA for FLUX.",
            status_code=400,
        )
