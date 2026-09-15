from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any

import httpx

from llm_provider.base import ImageResult, LLMProviderError, Message
from llm_provider.chat_util import translate_vendor_error

DEFAULT_BASE_URL = "https://apihub.agnes-ai.com/v1"
# https://wiki.agnes-ai.com/en/docs/agnes-image-25-flash.md
DEFAULT_IMAGE_MODEL = "agnes-image-2.5-flash"
DEFAULT_SIZE = "1K"
SUPPORTED_RATIOS = frozenset({"1:1", "3:4", "4:3", "16:9", "9:16", "2:3", "3:2", "21:9"})
PING_PROMPT = "solid electric lime square, beige studio, no text, no logos"


def agnes_ratio(aspect_ratio: str | None) -> str:
    raw = (aspect_ratio or "1:1").strip()
    if raw in SUPPORTED_RATIOS:
        return raw
    if raw == "4:5":
        return "3:4"
    return "1:1"


def _mime_for(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "image/webp"
    return "image/png"


def _decode_b64(raw: str) -> bytes:
    payload = raw.strip()
    if payload.startswith("data:") and "," in payload:
        payload = payload.split(",", 1)[1]
    return base64.b64decode(payload)


def _raise_status(status: int, body: str) -> None:
    class _Err(Exception):
        def __init__(self) -> None:
            super().__init__(body)
            self.status_code = status

    raise translate_vendor_error(_Err(), vendor="Agnes Image 2.5 Flash")


class AgnesImageProvider:
    """Agnes AI OpenAI-style /images/generations (pixels only)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_IMAGE_MODEL,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> str:
        del messages, temperature, max_tokens, reasoning_effort
        raise LLMProviderError(
            "Agnes Image 2.5 Flash paints pixels. Pick Gemini, DeepSeek, or GPT-OSS 20B for text.",
            status_code=400,
        )

    async def complete_stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        reasoning_effort: str | None = None,
    ) -> AsyncIterator[str]:
        del messages, temperature, max_tokens, reasoning_effort
        raise LLMProviderError(
            "Agnes Image 2.5 Flash paints pixels. Pick Gemini, DeepSeek, or GPT-OSS 20B for text.",
            status_code=400,
        )
        yield ""  # pragma: no cover — make this an async generator

    async def generate_image_concept(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
    ) -> str:
        del brief, style_hints
        raise LLMProviderError("Agnes Image 2.5 Flash does not write captions.", status_code=400)

    async def generate_image(
        self,
        brief: str,
        *,
        style_hints: list[str] | None = None,
        aspect_ratio: str | None = None,
    ) -> ImageResult:
        hints = ", ".join(style_hints) if style_hints else "none"
        prompt = f"{brief}\nStyle: {hints}."
        ratio = agnes_ratio(aspect_ratio)
        url = f"{self._base_url}/images/generations"
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt[:4000],
            "size": DEFAULT_SIZE,
            "ratio": ratio,
            "return_base64": True,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if response.status_code >= 400:
                    _raise_status(response.status_code, _error_text(response))
                try:
                    body = response.json()
                except Exception as exc:  # noqa: BLE001
                    raise LLMProviderError(
                        "Agnes Image 2.5 Flash returned a non-JSON body",
                        status_code=502,
                    ) from exc
                data = await _image_bytes(client, body)
        except httpx.RequestError as exc:
            raise LLMProviderError(
                f"Agnes Image 2.5 Flash unreachable ({exc.__class__.__name__})",
                status_code=502,
            ) from exc
        return ImageResult(mime_type=_mime_for(data), data=data)


def _error_text(response: httpx.Response) -> str:
    message = response.text[:800]
    try:
        err = response.json()
    except Exception:  # noqa: BLE001
        return message
    if isinstance(err, dict):
        blob = err.get("error") or err
        if isinstance(blob, dict):
            return str(blob.get("message") or message)
        if isinstance(blob, str) and blob.strip():
            return blob[:800]
    return message


async def _image_bytes(client: httpx.AsyncClient, body: object) -> bytes:
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list) or not rows:
        raise LLMProviderError(
            "Agnes Image 2.5 Flash returned no image. Try Generate again.",
            status_code=502,
        )
    first = rows[0] if isinstance(rows[0], dict) else {}
    b64 = first.get("b64_json") or first.get("b64")
    if isinstance(b64, str) and b64.strip():
        try:
            return _decode_b64(b64)
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(
                "Agnes Image 2.5 Flash returned unreadable image bytes.",
                status_code=502,
            ) from exc
    image_url = first.get("url")
    if isinstance(image_url, str) and image_url.strip():
        if image_url.startswith("data:"):
            return _decode_b64(image_url)
        fetched = await client.get(image_url)
        if fetched.status_code >= 400 or not fetched.content:
            raise LLMProviderError(
                "Agnes Image 2.5 Flash image URL could not be downloaded.",
                status_code=502,
            )
        return fetched.content
    raise LLMProviderError(
        "Agnes Image 2.5 Flash returned no image bytes. Try Generate again.",
        status_code=502,
    )
