"""X / Twitter via gallery-dl — timeline media + date filters."""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import store_bytes
from app.connectors.oss.common import (
    content_type_for,
    gallery_dl_date,
    pick_media_file,
    username_from_target,
)
from app.connectors.oss.netscape import write_netscape_cookies
from app.connectors.session_cookies import cookies_from_sessions
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


class GalleryDlError(RuntimeError):
    pass


@dataclass
class _Draft:
    post: RawPost
    media_path: Path | None


async def fetch_x_gallery_dl(
    *,
    run_id: str,
    handle: str,
    url: str,
    window: DateWindow,
    platform_sessions: dict[str, Any],
    object_store: ObjectStore | None,
    max_posts: int = 25,
) -> tuple[RawAccount, list[RawPost]]:
    cookies = cookies_from_sessions(platform_sessions, platforms={"x", "twitter"})
    if not cookies:
        raise GalleryDlError("no x/twitter connect cookies")

    with tempfile.TemporaryDirectory(prefix="rr-x-") as tmp:
        tmp_path = Path(tmp)
        account, drafts = await asyncio.to_thread(
            _fetch_sync,
            handle=handle,
            url=url,
            window=window,
            cookies=cookies,
            out_dir=tmp_path,
            max_posts=max_posts,
        )
        posts: list[RawPost] = []
        for draft in drafts:
            post = dict(draft.post)
            media_keys: list[str] = []
            image_url = post.get("image_url")
            if draft.media_path and draft.media_path.exists() and object_store is not None:
                key = await store_bytes(
                    object_store,
                    run_id=run_id,
                    post_id=str(post["external_post_id"]),
                    data=draft.media_path.read_bytes(),
                    content_type=content_type_for(draft.media_path),
                )
                if key:
                    media_keys = [key]
                    image_url = f"/ingestion/media/{key}"
            post["media_keys"] = media_keys
            post["image_url"] = image_url
            posts.append(post)  # type: ignore[arg-type]
        return account, posts


def _fetch_sync(
    *,
    handle: str,
    url: str,
    window: DateWindow,
    cookies: list[dict[str, Any]],
    out_dir: Path,
    max_posts: int,
) -> tuple[RawAccount, list[_Draft]]:
    username = username_from_target(handle, url)
    profile_url = url if "x.com" in url or "twitter.com" in url else f"https://x.com/{username}"
    cookie_file = out_dir / "cookies.txt"
    write_netscape_cookies(cookie_file, cookies)
    media_dir = out_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    # gallery-dl date-before is exclusive in some versions — use day after date_to
    from datetime import timedelta

    date_after = gallery_dl_date(window.date_from)
    date_before = gallery_dl_date(window.date_to + timedelta(days=1))

    cmd = [
        "gallery-dl",
        "--cookies",
        str(cookie_file),
        "--write-metadata",
        "--date-after",
        date_after,
        "--date-before",
        date_before,
        "--range",
        f"1-{max_posts}",
        "-d",
        str(media_dir),
        "--no-mtime",
        profile_url,
    ]
    import subprocess

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25, check=False)
    if proc.returncode not in (0, 1):  # 1 = partial
        err = (proc.stderr or proc.stdout or "gallery-dl failed")[:500]
        if "AuthRequired" in err or "authenticated cookies" in err:
            raise GalleryDlError(f"auth required: {err}")
        raise GalleryDlError(err)

    account = RawAccount(
        handle=f"@{username}"[:100],
        display_name=username[:200],
        platform="x",
    )

    # Pair metadata JSON with media files
    meta_files = list(media_dir.rglob("*.json")) + list(media_dir.rglob("*.jsonl"))
    drafts: list[_Draft] = []
    seen: set[str] = set()

    for meta_path in meta_files:
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            tweet_id = str(item.get("tweet_id") or item.get("id") or item.get("status") or "")
            if not tweet_id or tweet_id in seen:
                continue
            seen.add(tweet_id)
            posted = _posted_from_meta(item)
            if posted and not window.contains(posted):
                continue
            if posted is None:
                posted = datetime.now(UTC)

            likes = int(item.get("favorite_count") or item.get("likes") or 0)
            comments = int(item.get("reply_count") or item.get("comments") or 0)
            shares = int(item.get("retweet_count") or item.get("shares") or 0)
            views = int(item.get("view_count") or item.get("views") or 0)
            caption = str(item.get("content") or item.get("description") or item.get("text") or "")[
                :2000
            ]
            post_url = str(
                item.get("post_url")
                or item.get("url")
                or f"https://x.com/{username}/status/{tweet_id}"
            )
            media_path = pick_media_file(meta_path.parent, stem_hints=[tweet_id, meta_path.stem])
            raw = RawPost(
                account_handle=account["handle"],
                external_post_id=f"x:{tweet_id}"[:100],
                format="founder_post",
                theme_tags=[
                    "x",
                    "source:gallery_dl",
                    f"link:{post_url[:180]}",
                    f"date_from:{window.date_from.isoformat()}",
                    f"date_to:{window.date_to.isoformat()}",
                ],
                caption=caption or f"@{username} post",
                image_url=None,
                likes=likes,
                comments=comments,
                shares=shares,
                views=views,
                posted_at=posted.isoformat().replace("+00:00", "Z"),
                media_urls=[],
                media_keys=[],
            )
            drafts.append(_Draft(post=raw, media_path=media_path))
            if len(drafts) >= max_posts:
                break
        if len(drafts) >= max_posts:
            break

    # Fallback: media files without parseable metadata
    if not drafts:
        for media in sorted(media_dir.rglob("*")):
            if not media.is_file() or media.suffix.lower() in {".json", ".jsonl", ".txt"}:
                continue
            stem = media.stem
            raw = RawPost(
                account_handle=account["handle"],
                external_post_id=f"x:{stem}"[:100],
                format="founder_post",
                theme_tags=["x", "source:gallery_dl", "posted_at_uncertain"],
                caption=f"@{username} media",
                image_url=None,
                likes=0,
                comments=0,
                shares=0,
                views=0,
                posted_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                media_urls=[],
                media_keys=[],
            )
            drafts.append(_Draft(post=raw, media_path=media))
            if len(drafts) >= max_posts:
                break

    if not drafts and "AuthRequired" in (proc.stderr or ""):
        raise GalleryDlError("authenticated cookies needed")
    return account, drafts


def _posted_from_meta(item: dict[str, Any]) -> datetime | None:
    for key in ("date", "timestamp", "date_utc", "created_at", "upload_date"):
        val = item.get(key)
        if val is None:
            continue
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(float(val), tz=UTC)
        if isinstance(val, str):
            text = val.strip().replace("Z", "+00:00")
            if len(text) == 8 and text.isdigit():
                return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), tzinfo=UTC)
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                continue
    return None
