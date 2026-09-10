from __future__ import annotations

import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

import anyio


class ObjectStore(Protocol):
    """Blob storage for generated artifacts (recordings, screenshots).

    Local disk in dev; the interface is deliberately narrow so an
    S3-compatible store can be swapped in later without touching callers.
    """

    async def put(self, key: str, source_path: Path) -> str: ...

    def open(self, key: str) -> AsyncIterator[bytes]: ...

    def resolve_path(self, key: str) -> Path: ...


class LocalDiskObjectStore:
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def resolve_path(self, key: str) -> Path:
        return self._root / key

    async def put(self, key: str, source_path: Path) -> str:
        dest = self.resolve_path(key)

        def _move() -> None:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(dest))

        await anyio.to_thread.run_sync(_move)
        return key

    async def open(self, key: str) -> AsyncIterator[bytes]:
        path = self.resolve_path(key)
        async with await anyio.open_file(path, "rb") as f:
            while chunk := await f.read(65536):
                yield chunk
