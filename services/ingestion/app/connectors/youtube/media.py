"""Download post media + top comments for YouTube posts."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.connectors.base import CommentSample, RawPost
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


def best_thumbnail_url(video_id: str, snippet_thumbs: dict[str, Any] | None = None) -> str | None:
    """Prefer maxres CDN still, then API thumbnails, then hqdefault."""
    candidates: list[str] = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    ]
    if snippet_thumbs:
        for key in ("maxres", "standard", "high", "medium", "default"):
            url = (snippet_thumbs.get(key) or {}).get("url")
            if url:
                candidates.insert(0, url)
    return candidates[0] if candidates else None


async def fetch_top_comments(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    video_id: str,
    limit: int = 10,
) -> list[CommentSample]:
    try:
        response = await client.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "maxResults": str(limit),
                "textFormat": "plainText",
                "key": api_key,
            },
            timeout=20.0,
        )
        if response.status_code >= 400:
            logger.info("commentThreads failed for %s: %s", video_id, response.status_code)
            return []
        data = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.info("commentThreads error for %s: %s", video_id, exc)
        return []

    samples: list[CommentSample] = []
    for item in data.get("items") or []:
        top = (item.get("snippet") or {}).get("topLevelComment", {}).get("snippet") or {}
        text = (top.get("textDisplay") or top.get("textOriginal") or "").strip()
        if not text:
            continue
        samples.append(
            CommentSample(
                author=str(top.get("authorDisplayName") or "viewer")[:120],
                text=text[:500],
                likes=int(top.get("likeCount") or 0),
            )
        )
    samples.sort(key=lambda c: c["likes"], reverse=True)
    return samples[:limit]


async def download_media_to_store(
    store: ObjectStore,
    *,
    run_id: str,
    post_id: str,
    url: str,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Fetch remote media bytes and store under media/{run_id}/{post_id}.*"""
    owns = client is None
    http = client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)
    try:
        response = await http.get(url)
        if response.status_code >= 400 or not response.content:
            return None
        content_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"
        elif "gif" in content_type:
            ext = ".gif"
        key = f"media/{run_id}/{post_id}{ext}"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)
        try:
            return await store.put(key, tmp_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)  # noqa: ASYNC240
            raise
    except Exception as exc:  # noqa: BLE001
        logger.info("media download failed for %s: %s", post_id, exc)
        return None
    finally:
        if owns:
            await http.aclose()


async def enrich_posts_media(
    posts: list[RawPost],
    *,
    run_id: str,
    store: ObjectStore | None = None,
    api_key: str | None = None,
) -> list[RawPost]:
    """Attach media_keys + optional comment_sample; prefer local media URL for Findings."""
    if not posts:
        return posts
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        enriched: list[RawPost] = []
        for post in posts:
            updated = dict(post)
            vid = post["external_post_id"]
            urls = list(post.get("media_urls") or [])
            if post.get("image_url") and post["image_url"] not in urls:
                urls.insert(0, post["image_url"])
            if not urls:
                thumb = best_thumbnail_url(vid)
                if thumb:
                    urls = [thumb]
            updated["media_urls"] = urls

            keys: list[str] = list(post.get("media_keys") or [])
            if store and urls and not keys:
                key = await download_media_to_store(
                    store, run_id=run_id, post_id=vid, url=urls[0], client=http
                )
                if key:
                    keys = [key]
                    updated["image_url"] = f"/ingestion/media/{key}"
            updated["media_keys"] = keys

            if api_key and not post.get("comment_sample"):
                comments = await fetch_top_comments(http, api_key=api_key, video_id=vid)
                if comments:
                    updated["comment_sample"] = comments
            enriched.append(updated)  # type: ignore[arg-type]
        return enriched
