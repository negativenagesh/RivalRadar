"""yt-dlp primary OSS path for YouTube (preferred over scrapetube in tests).

scrapetube returned 0 videos for @PixisAI; yt-dlp with android player client
returns upload_date, view_count, like_count and can download MP4s.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import store_bytes
from app.connectors.oss.common import content_type_for, ytdlp_yyyymmdd
from app.connectors.youtube.media import best_thumbnail_url
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


class YtDlpError(RuntimeError):
    pass


async def fetch_channel_via_ytdlp(
    url_or_handle: str,
    *,
    window: DateWindow,
    max_entries: int = 25,
    run_id: str | None = None,
    object_store: ObjectStore | None = None,
    download_media: bool = True,
) -> tuple[RawAccount, list[RawPost]]:
    """Channel uploads in date window via yt-dlp (metadata + optional media)."""
    target = url_or_handle.strip()
    if target.startswith("@"):
        target = f"https://www.youtube.com/{target}/videos"
    elif "youtube.com" in target and "/videos" not in target and "/watch" not in target:
        target = target.rstrip("/") + "/videos"

    dateafter = ytdlp_yyyymmdd(window.date_from)
    datebefore = ytdlp_yyyymmdd(window.date_to)

    with tempfile.TemporaryDirectory(prefix="rr-yt-") as tmp:
        out_dir = Path(tmp)
        cmd = [
            "yt-dlp",
            "--playlist-end",
            str(max_entries),
            "--dateafter",
            dateafter,
            "--datebefore",
            datebefore,
            "--extractor-args",
            "youtube:player_client=android,web",
            "--write-info-json",
            "--write-thumbnail",
            "--convert-thumbnails",
            "jpg",
            "--no-warnings",
            "-f",
            "best[ext=mp4]/best[height<=720]/best",
            "-o",
            str(out_dir / "%(id)s.%(ext)s"),
        ]
        if not download_media or object_store is None:
            cmd.append("--skip-download")
            # Still need info — use print-to-file via dump
            cmd = [
                "yt-dlp",
                "--playlist-end",
                str(max_entries),
                "--dateafter",
                dateafter,
                "--datebefore",
                datebefore,
                "--extractor-args",
                "youtube:player_client=android,web",
                "--skip-download",
                "--print",
                "%()j",
                "--no-warnings",
                target,
            ]
            return await _fetch_print_json(cmd, window=window)

        cmd.append(target)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _stdout, stderr = await proc.communicate()
        if proc.returncode not in (0, 1):
            # Fallback to metadata-only print path
            logger.warning("yt-dlp download path failed: %s", stderr.decode()[:300])
            return await fetch_channel_via_ytdlp(
                url_or_handle,
                window=window,
                max_entries=max_entries,
                run_id=run_id,
                object_store=None,
                download_media=False,
            )

        parsed = await asyncio.to_thread(_parse_download_dir, out_dir, window)
        if parsed is None:
            return await fetch_channel_via_ytdlp(
                url_or_handle,
                window=window,
                max_entries=max_entries,
                download_media=False,
            )
        account, drafts = parsed
        posts: list[RawPost] = []
        for draft in drafts:
            post = dict(draft["post"])
            media_keys: list[str] = []
            image_url = post.get("image_url")
            media_bytes = draft.get("media_bytes")
            media_ctype = draft.get("media_ctype") or "video/mp4"
            if media_bytes and object_store is not None and run_id:
                key = await store_bytes(
                    object_store,
                    run_id=run_id,
                    post_id=str(post["external_post_id"]),
                    data=media_bytes,
                    content_type=str(media_ctype),
                )
                if key:
                    media_keys = [key]
                    image_url = f"/ingestion/media/{key}"
            post["media_keys"] = media_keys
            post["image_url"] = image_url
            posts.append(post)  # type: ignore[arg-type]
        return account, posts


def _parse_download_dir(
    out_dir: Path, window: DateWindow
) -> tuple[RawAccount, list[dict[str, Any]]] | None:
    info_files = [p for p in out_dir.glob("*.info.json") if not p.name.startswith("UC")]
    if not info_files:
        info_files = [
            p
            for p in out_dir.glob("*.info.json")
            if "entries" not in p.read_text(encoding="utf-8")[:80]
        ]

    account: RawAccount | None = None
    drafts: list[dict[str, Any]] = []
    for info_path in info_files:
        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if payload.get("entries"):
            continue
        vid = payload.get("id")
        if not vid:
            continue
        channel = payload.get("channel") or payload.get("uploader") or "YouTube"
        handle = payload.get("uploader_id") or payload.get("channel_id") or "youtube"
        if not str(handle).startswith("@"):
            handle = f"@{handle}"
        if account is None:
            account = RawAccount(
                handle=str(handle)[:100],
                display_name=str(channel)[:200],
                platform="youtube",
            )

        posted = _posted_from_payload(payload)
        if posted is None or not window.contains(posted):
            continue

        views = int(payload.get("view_count") or 0)
        likes = int(payload.get("like_count") or 0)
        comments = int(payload.get("comment_count") or 0)
        title = payload.get("title") or "Untitled"
        desc = (payload.get("description") or "")[:400]
        watch = f"https://www.youtube.com/watch?v={vid}"
        thumb = best_thumbnail_url(str(vid))
        media_urls: list[str] = [thumb] if thumb else []

        media_file = _find_media(out_dir, str(vid))
        media_bytes: bytes | None = None
        media_ctype = "video/mp4"
        if media_file and media_file.exists():
            media_bytes = media_file.read_bytes()
            media_ctype = content_type_for(media_file)
        else:
            thumb_file = out_dir / f"{vid}.jpg"
            if thumb_file.exists():
                media_bytes = thumb_file.read_bytes()
                media_ctype = "image/jpeg"

        assert account is not None
        raw = RawPost(
            account_handle=account["handle"],
            external_post_id=str(vid),
            format="founder_post",
            theme_tags=[
                "youtube",
                "video",
                "source:yt_dlp",
                f"views:{views}",
                f"link:{watch}",
                f"date_from:{window.date_from.isoformat()}",
                f"date_to:{window.date_to.isoformat()}",
            ],
            caption=f"{title}\n\n{desc}".strip(),
            image_url=thumb,
            likes=likes,
            comments=comments,
            shares=0,
            posted_at=posted.isoformat().replace("+00:00", "Z"),
            views=views,
            media_urls=media_urls,
            media_keys=[],
        )
        drafts.append(
            {"post": raw, "media_bytes": media_bytes, "media_ctype": media_ctype}
        )

    if account is None:
        return None
    return account, drafts


async def _fetch_print_json(
    cmd: list[str],
    *,
    window: DateWindow,
) -> tuple[RawAccount, list[RawPost]]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode not in (0, 1):
        raise YtDlpError(stderr.decode("utf-8", errors="replace")[:400] or "yt-dlp failed")

    lines = [ln for ln in stdout.decode("utf-8", errors="replace").splitlines() if ln.strip()]
    account: RawAccount | None = None
    posts: list[RawPost] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("_type") == "playlist" or entry.get("entries"):
            continue
        vid = entry.get("id")
        if not vid:
            continue
        channel = entry.get("channel") or entry.get("uploader") or "YouTube"
        handle = entry.get("uploader_id") or entry.get("channel_id") or "youtube"
        if not str(handle).startswith("@"):
            handle = f"@{handle}"
        if account is None:
            account = RawAccount(
                handle=str(handle)[:100],
                display_name=str(channel)[:200],
                platform="youtube",
            )
        posted = _posted_from_payload(entry)
        if posted is None or not window.contains(posted):
            continue
        views = int(entry.get("view_count") or 0)
        likes = int(entry.get("like_count") or 0)
        comments = int(entry.get("comment_count") or 0)
        title = entry.get("title") or "Untitled"
        desc = (entry.get("description") or "")[:400]
        thumb = best_thumbnail_url(str(vid))
        watch = f"https://www.youtube.com/watch?v={vid}"
        posts.append(
            RawPost(
                account_handle=account["handle"],
                external_post_id=str(vid),
                format="founder_post",
                theme_tags=[
                    "youtube",
                    "video",
                    "source:yt_dlp",
                    f"views:{views}",
                    f"link:{watch}",
                    f"date_from:{window.date_from.isoformat()}",
                    f"date_to:{window.date_to.isoformat()}",
                ],
                caption=f"{title}\n\n{desc}".strip(),
                image_url=thumb,
                likes=likes,
                comments=comments,
                shares=0,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
                views=views,
                media_urls=[thumb] if thumb else [],
            )
        )

    if account is None:
        # Last resort: flat playlist (no metrics) — keep old behavior
        return await _flat_playlist_fallback(cmd[-1] if cmd else "", window=window)
    return account, posts


async def _flat_playlist_fallback(
    target: str,
    *,
    window: DateWindow,
    max_entries: int = 25,
) -> tuple[RawAccount, list[RawPost]]:
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
    for entry in payload.get("entries") or []:
        if not entry:
            continue
        vid = entry.get("id")
        if not vid:
            continue
        posted = _posted_from_payload(entry)
        if posted is None or not window.contains(posted):
            continue
        views = int(entry.get("view_count") or 0)
        likes = int(entry.get("like_count") or 0)
        comments = int(entry.get("comment_count") or 0)
        vtitle = entry.get("title") or "Untitled"
        thumb = best_thumbnail_url(str(vid))
        watch = f"https://www.youtube.com/watch?v={vid}"
        posts.append(
            RawPost(
                account_handle=account["handle"],
                external_post_id=str(vid),
                format="founder_post",
                theme_tags=["youtube", "video", "source:yt_dlp", f"views:{views}", f"link:{watch}"],
                caption=str(vtitle),
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


def _posted_from_payload(payload: dict[str, Any]) -> datetime | None:
    upload = payload.get("upload_date")
    if isinstance(upload, str) and len(upload) == 8 and upload.isdigit():
        return datetime(int(upload[0:4]), int(upload[4:6]), int(upload[6:8]), tzinfo=UTC)
    ts = payload.get("timestamp") or payload.get("release_timestamp")
    if ts is not None:
        try:
            return datetime.fromtimestamp(int(ts), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None
    return None


def _find_media(folder: Path, vid: str) -> Path | None:
    for ext in (".mp4", ".webm", ".mkv", ".m4a"):
        p = folder / f"{vid}{ext}"
        if p.exists():
            return p
    matches = list(folder.glob(f"{vid}.*"))
    for p in matches:
        if p.suffix.lower() in {".mp4", ".webm", ".mkv"}:
            return p
    return None
