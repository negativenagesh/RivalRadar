"""Merge multiple Connector implementations into one run."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.connectors.base import RawAccount, RawPost


class CompositeConnector:
    def __init__(self, connectors: list[Any]) -> None:
        self._connectors = connectors

    @property
    def recorded_video_path(self) -> Path | None:
        for c in self._connectors:
            path = getattr(c, "recorded_video_path", None)
            if isinstance(path, Path):
                return path
        return None

    @property
    def sources_used(self) -> list[str]:
        out: list[str] = []
        for c in self._connectors:
            used = getattr(c, "sources_used", None)
            if used:
                out.extend(used)
            elif c.__class__.__name__ == "SocialProfileConnector":
                out.append("mock")
        return out

    @property
    def screenshot_keys(self) -> list[str]:
        out: list[str] = []
        for c in self._connectors:
            keys = getattr(c, "screenshot_keys", None)
            if keys:
                out.extend(keys)
        return out

    async def fetch_accounts(self) -> list[RawAccount]:
        accounts: list[RawAccount] = []
        for c in self._connectors:
            accounts.extend(await c.fetch_accounts())
        return accounts

    async def fetch_posts(self) -> list[RawPost]:
        posts: list[RawPost] = []
        for c in self._connectors:
            posts.extend(await c.fetch_posts())
        return posts

    async def aclose(self) -> None:
        for c in self._connectors:
            aclose = getattr(c, "aclose", None)
            if aclose is not None:
                await aclose()
