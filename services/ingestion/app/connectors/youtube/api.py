"""YouTube Data API v3 client (official, quota-based)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.connectors.base import RawAccount, RawPost

API_BASE = "https://www.googleapis.com/youtube/v3"


class YouTubeApiError(RuntimeError):
    pass


class YouTubeDataClient:
    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> YouTubeDataClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()

    async def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        assert self._client is not None
        merged = {**params, "key": self._api_key}
        response = await self._client.get(f"{API_BASE}/{path}", params=merged)
        if response.status_code >= 400:
            raise YouTubeApiError(f"YouTube API {path} failed: {response.status_code} {response.text[:200]}")
        data: dict[str, Any] = response.json()
        return data

    async def resolve_channel(self, *, handle: str, channel_id: str | None) -> dict[str, Any]:
        if channel_id:
            data = await self._get("channels", {"part": "snippet,statistics,contentDetails", "id": channel_id})
        else:
            data = await self._get(
                "channels",
                {"part": "snippet,statistics,contentDetails", "forHandle": handle.lstrip("@")},
            )
        items = data.get("items") or []
        if not items:
            # Fallback search for older custom URLs
            search = await self._get(
                "search",
                {"part": "snippet", "type": "channel", "q": handle.lstrip("@"), "maxResults": "1"},
            )
            search_items = search.get("items") or []
            if not search_items:
                raise YouTubeApiError(f"Channel not found for {handle}")
            found_id = search_items[0]["snippet"]["channelId"]
            data = await self._get("channels", {"part": "snippet,statistics,contentDetails", "id": found_id})
            items = data.get("items") or []
            if not items:
                raise YouTubeApiError(f"Channel not found for {handle}")
        channel: dict[str, Any] = items[0]
        return channel

    async def fetch_recent_videos(
        self,
        channel: dict[str, Any],
        *,
        lookback_days: int,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        uploads = (
            channel.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        )
        if not uploads:
            return []
        playlist = await self._get(
            "playlistItems",
            {
                "part": "contentDetails,snippet",
                "playlistId": uploads,
                "maxResults": str(max_results),
            },
        )
        video_ids = [
            item["contentDetails"]["videoId"]
            for item in playlist.get("items") or []
            if item.get("contentDetails", {}).get("videoId")
        ]
        if not video_ids:
            return []

        details = await self._get(
            "videos",
            {
                "part": "snippet,statistics,contentDetails",
                "id": ",".join(video_ids),
            },
        )
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
        kept: list[dict[str, Any]] = []
        for item in details.get("items") or []:
            published = item["snippet"]["publishedAt"]
            posted = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if posted >= cutoff:
                kept.append(item)
        return kept


def channel_to_raw_account(channel: dict[str, Any], source: str) -> RawAccount:
    snippet = channel["snippet"]
    custom = snippet.get("customUrl") or channel["id"]
    handle = custom if custom.startswith("@") else f"@{custom.lstrip('@')}"
    return RawAccount(
        handle=handle[:100],
        display_name=snippet.get("title") or handle,
        platform="youtube",
    )


def video_to_raw_post(
    video: dict[str, Any],
    *,
    account_handle: str,
    source: str,
) -> RawPost:
    snippet = video["snippet"]
    stats = video.get("statistics") or {}
    title = snippet.get("title") or "Untitled"
    desc = (snippet.get("description") or "")[:400]
    thumbs = snippet.get("thumbnails") or {}
    thumb = (
        (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    )
    likes = int(stats.get("likeCount") or 0)
    comments = int(stats.get("commentCount") or 0)
    views = int(stats.get("viewCount") or 0)
    published = snippet["publishedAt"]
    return RawPost(
        account_handle=account_handle,
        external_post_id=video["id"],
        format="founder_post",
        theme_tags=["youtube", "video", f"source:{source}", f"views:{views}"],
        caption=f"{title}\n\n{desc}".strip(),
        image_url=thumb,
        likes=likes,
        comments=comments,
        shares=views,  # views ride in shares slot for heat scoring until schema expands
        posted_at=published,
    )
