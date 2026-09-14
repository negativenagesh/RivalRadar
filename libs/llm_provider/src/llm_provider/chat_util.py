from __future__ import annotations

import re
from typing import Any

from llm_provider.base import LLMProviderError

_RETRY_IN = re.compile(r"retry in ([\d.]+)\s*s", re.I)


def message_text(message: Any) -> str:
    """Prefer visible content; gpt-oss may park the draft in reasoning_content."""
    content = getattr(message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        bits: list[str] = []
        for part in content:
            if isinstance(part, str) and part.strip():
                bits.append(part.strip())
            elif isinstance(part, dict) and str(part.get("text") or "").strip():
                bits.append(str(part["text"]).strip())
            else:
                text = getattr(part, "text", None)
                if isinstance(text, str) and text.strip():
                    bits.append(text.strip())
        if bits:
            return "\n".join(bits)
    reasoning = getattr(message, "reasoning_content", None)
    if isinstance(reasoning, str) and reasoning.strip():
        return reasoning.strip()
    return ""


def translate_vendor_error(exc: BaseException, *, vendor: str) -> LLMProviderError:
    status = int(getattr(exc, "status_code", 0) or 0)
    raw = str(exc)
    retry_after: int | None = None
    match = _RETRY_IN.search(raw)
    if match:
        retry_after = max(1, int(float(match.group(1))))
    wait = (
        f" Wait ~{retry_after}s and Generate again."
        if retry_after
        else " Wait a minute and Generate again."
    )
    if status == 429:
        return LLMProviderError(
            f"{vendor} rate limit." + wait,
            status_code=429,
            retry_after=retry_after,
        )
    if status in {401, 403}:
        return LLMProviderError(
            f"{vendor} rejected this API key. Re-paste it in the Models chip.",
            status_code=401,
        )
    if status == 400:
        return LLMProviderError(f"{vendor} request failed: {raw[:240]}", status_code=400)
    return LLMProviderError(f"{vendor} request failed. Try Generate again.", status_code=502)
