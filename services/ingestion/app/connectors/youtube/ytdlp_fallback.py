"""yt-dlp fallback when YouTube Data API is unavailable."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.connectors.base import RawAccount, RawPost

logger = logging.getLogger(__name__)


class YtDlpError(RuntimeError):
    pass


async def fetch_channel_via_ytdlp(
    url_or_handle: str,
    *,
    lookback_days: int,
    max_entries: int = 25,
) -> tuple[RawAccount, list[RawPost]]:
    """Extract channel + recent uploads via yt-dlp flat playlist JSON.

    Expect breakage vs the official API — used only as fallback.
    """
    target = url_or_handle.strip()
    if target.startswith("@"):
        target = f"https://www.youtube.com/{target}/videos"
    elif "youtube.com" in target and "/videos" not in target:
        target = target.rstrip("/") + "/videos"

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        "--playlist-end",
        str(max_entries),
        "--no-warnings",
        target,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise YtDlpError(stderr.decode("utf-8", errors="replace")[:400] or "yt-dlp failed")

    try:
        payload = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise YtDlpError("yt-dlp returned non-JSON") from exc

    title = payload.get("channel") or payload.get("uploader") or payload.get("title") or "YouTube"
    channel_id = payload.get("channel_id") or payload.get("id") or "youtube"
    handle = payload.get("uploader_id") or channel_id
    if not str(handle).startswith("@"):
        handle = f"@{handle}"
    account = RawAccount(handle=handle[:100], display_name=str(title)[:200], platform="youtube")

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    posts: list[RawPost] = []
    entries: list[dict[str, Any]] = payload.get("entries") or []
    for entry in entries:
        if not entry:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        ts = entry.get("timestamp") or entry.get("release_timestamp")
        posted = (
            datetime.fromtimestamp(int(ts), tz=UTC) if ts is not None else datetime.now(UTC)
        )
        if posted < cutoff:
            continue
        views = int(entry.get("view_count") or 0)
        likes = int(entry.get("like_count") or 0)
        comments = int(entry.get("comment_count") or 0)
        vtitle = entry.get("title") or "Untitled"
        desc = (entry.get("description") or "")[:400]
        thumb = None
        thumbs = entry.get("thumbnails") or []
        if thumbs:
            thumb = thumbs[-1].get("url")
        posts.append(
            RawPost(
                account_handle=account["handle"],
                external_post_id=str(vid),
                format="founder_post",
                theme_tags=["youtube", "video", "source:yt_dlp", f"views:{views}"],
                caption=f"{vtitle}\n\n{desc}".strip(),
                image_url=thumb,
                likes=likes,
                comments=comments,
                shares=views,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
            )
        )
    return account, posts
