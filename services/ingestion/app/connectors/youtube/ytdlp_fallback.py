"""yt-dlp fallback when YouTube Data API is unavailable."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.connectors.base import RawAccount, RawPost
from app.connectors.youtube.media import best_thumbnail_url
from app.date_window import DateWindow

logger = logging.getLogger(__name__)


class YtDlpError(RuntimeError):
    pass


async def fetch_channel_via_ytdlp(
    url_or_handle: str,
    *,
    window: DateWindow,
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
        if not window.contains(posted):
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
        if not thumb:
            thumb = best_thumbnail_url(str(vid))
        watch = f"https://www.youtube.com/watch?v={vid}"
        posts.append(
            RawPost(
                account_handle=account["handle"],
                external_post_id=str(vid),
                format="founder_post",
                theme_tags=["youtube", "video", "source:yt_dlp", f"views:{views}", f"link:{watch}"],
                caption=f"{vtitle}\n\n{desc}".strip(),
                image_url=thumb,
                likes=likes,
                comments=comments,
                shares=0,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
                views=views,
                media_urls=[thumb] if thumb else [],
            )
        )
    return account, posts
