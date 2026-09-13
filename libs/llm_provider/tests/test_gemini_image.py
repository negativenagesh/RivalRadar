from __future__ import annotations

import base64
from typing import Any

import pytest

from llm_provider.base import LLMProviderError
from llm_provider.gemini import GeminiOpenAICompatProvider, native_gemini_root


def test_native_gemini_root_strips_openai_compat_suffix() -> None:
    assert (
        native_gemini_root("https://generativelanguage.googleapis.com/v1beta/openai/")
        == "https://generativelanguage.googleapis.com/v1beta"
    )
    assert (
        native_gemini_root("https://generativelanguage.googleapis.com/v1beta")
        == "https://generativelanguage.googleapis.com/v1beta"
    )


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | str) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = payload if isinstance(payload, str) else __import__("json").dumps(payload)

    def json(self) -> dict[str, Any]:
        if isinstance(self._payload, str):
            raise ValueError("not json")
        return self._payload


class _FakeAsyncClient:
    last_url: str | None = None
    last_json: dict[str, Any] | None = None
    last_headers: dict[str, str] | None = None
    response: _FakeResponse = _FakeResponse(200, {})

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> _FakeResponse:
        type(self).last_url = url
        type(self).last_json = json
        type(self).last_headers = headers
        return self.response


def _png_payload(raw: bytes = b"fake-png-bytes") -> dict[str, Any]:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "ok"},
                        {
                            "inlineData": {
                                "mimeType": "image/png",
                                "data": base64.b64encode(raw).decode(),
                            }
                        },
                    ]
                }
            }
        ]
    }


async def test_generate_image_uses_native_generate_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_bytes = b"fake-png-bytes"
    _FakeAsyncClient.response = _FakeResponse(200, _png_payload(raw_bytes))
    monkeypatch.setattr("llm_provider.gemini.httpx.AsyncClient", _FakeAsyncClient)

    provider = GeminiOpenAICompatProvider(
        api_key="k",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
    result = await provider.generate_image(
        "a meme about mondays",
        style_hints=["bold", "gen-z"],
        aspect_ratio="4:5",
    )

    assert result.mime_type == "image/png"
    assert result.data == raw_bytes
    assert _FakeAsyncClient.last_url == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-image:generateContent"
    )
    assert _FakeAsyncClient.last_headers is not None
    assert _FakeAsyncClient.last_headers["x-goog-api-key"] == "k"
    body = _FakeAsyncClient.last_json or {}
    assert body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "4:5"


async def test_generate_image_accepts_snake_case_inline_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_bytes = b"snake"
    _FakeAsyncClient.response = _FakeResponse(
        200,
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/jpeg",
                                    "data": base64.b64encode(raw_bytes).decode(),
                                }
                            }
                        ]
                    }
                }
            ]
        },
    )
    monkeypatch.setattr("llm_provider.gemini.httpx.AsyncClient", _FakeAsyncClient)
    provider = GeminiOpenAICompatProvider(api_key="k", base_url="https://example.test/v1beta/openai")
    result = await provider.generate_image("brief")
    assert result.mime_type == "image/jpeg"
    assert result.data == raw_bytes


async def test_generate_image_raises_when_no_image_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAsyncClient.response = _FakeResponse(
        200, {"candidates": [{"content": {"parts": [{"text": "no pixels"}]}}]}
    )
    monkeypatch.setattr("llm_provider.gemini.httpx.AsyncClient", _FakeAsyncClient)
    provider = GeminiOpenAICompatProvider(api_key="k", base_url="https://example.test")
    with pytest.raises(LLMProviderError, match="no image bytes"):
        await provider.generate_image("a brief")


async def test_generate_image_maps_429(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeAsyncClient.response = _FakeResponse(
        429,
        {"error": {"message": "Quota exceeded. Please retry in 12.4s."}},
    )
    monkeypatch.setattr("llm_provider.gemini.httpx.AsyncClient", _FakeAsyncClient)
    provider = GeminiOpenAICompatProvider(api_key="k", base_url="https://example.test")
    with pytest.raises(LLMProviderError) as excinfo:
        await provider.generate_image("a brief")
    assert excinfo.value.status_code == 429
    assert "Nano Banana 2" in excinfo.value.detail
    assert "12s" in excinfo.value.detail
