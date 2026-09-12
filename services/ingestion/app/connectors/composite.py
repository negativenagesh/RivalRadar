"""Merge multiple Connector implementations into one run.

YouTube/yt-dlp and Playwright platform scouts run concurrently via gather.
"""

from __future__ import annotations

import asyncio
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
        batches = await asyncio.gather(*(c.fetch_accounts() for c in self._connectors))
        accounts: list[RawAccount] = []
        for batch in batches:
            accounts.extend(batch)
        return accounts

    async def fetch_posts(self) -> list[RawPost]:
        batches = await asyncio.gather(*(c.fetch_posts() for c in self._connectors))
        posts: list[RawPost] = []
        for batch in batches:
            posts.extend(batch)
        return posts

    async def aclose(self) -> None:
        await asyncio.gather(
            *[
                c.aclose()
                for c in self._connectors
                if getattr(c, "aclose", None) is not None
            ],
            return_exceptions=True,
        )
