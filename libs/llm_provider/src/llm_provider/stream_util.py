"""Shared OpenAI-compat chat streaming helper."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from llm_provider.base import Message
from llm_provider.chat_util import translate_transport_error, translate_vendor_error


async def stream_chat_deltas(
    client: AsyncOpenAI,
    *,
    model: str,
    messages: list[Message],
    temperature: float,
    max_tokens: int,
    vendor: str,
    extra_body: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    """Yield text deltas from an OpenAI-compat chat.completions stream."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": cast(
            list[ChatCompletionMessageParam],
            [{"role": m.role, "content": m.content} for m in messages],
        ),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    try:
        stream = await client.chat.completions.create(**kwargs)
    except APIStatusError as exc:
        raise translate_vendor_error(exc, vendor=vendor) from exc
    except (APITimeoutError, APIConnectionError) as exc:
        raise translate_transport_error(exc, vendor=vendor) from exc

    try:
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            piece = getattr(delta, "content", None)
            if isinstance(piece, str) and piece:
                yield piece
                continue
            # gpt-oss may stream into reasoning_content before visible content.
            reasoning = getattr(delta, "reasoning_content", None)
            if isinstance(reasoning, str) and reasoning:
                yield reasoning
    except (APITimeoutError, APIConnectionError) as exc:
        raise translate_transport_error(exc, vendor=vendor) from exc