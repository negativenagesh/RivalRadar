from collections.abc import AsyncIterator
from typing import Any

import pytest

from llm_provider.base import Message
from llm_provider.stream_util import stream_chat_deltas


class _Delta:
    def __init__(self, content: str | None = None, reasoning_content: str | None = None) -> None:
        self.content = content
        self.reasoning_content = reasoning_content


class _Choice:
    def __init__(self, delta: _Delta) -> None:
        self.delta = delta


class _Chunk:
    def __init__(self, text: str) -> None:
        self.choices = [_Choice(_Delta(content=text))]


class _FakeStream:
    def __init__(self, pieces: list[str]) -> None:
        self._pieces = pieces

    def __aiter__(self) -> AsyncIterator[Any]:
        async def _gen() -> AsyncIterator[Any]:
            for piece in self._pieces:
                yield _Chunk(piece)

        return _gen()


class _FakeClient:
    def __init__(self, pieces: list[str]) -> None:
        self._pieces = pieces
        self.chat = self
        self.completions = self

    async def create(self, **kwargs: Any) -> _FakeStream:
        assert kwargs.get("stream") is True
        return _FakeStream(self._pieces)


@pytest.mark.asyncio
async def test_stream_chat_deltas_yields_content_pieces() -> None:
    client = _FakeClient(["Hello", " ", "world"])
    out: list[str] = []
    async for piece in stream_chat_deltas(
        client,  # type: ignore[arg-type]
        model="test",
        messages=[Message(role="user", content="hi")],
        temperature=0.2,
        max_tokens=64,
        vendor="test",
    ):
        out.append(piece)
    assert "".join(out) == "Hello world"
