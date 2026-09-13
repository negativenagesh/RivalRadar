"""Instagram via Instaloader — captions, media, metrics, date filter."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

from app.connectors.base import RawAccount, RawPost
from app.connectors.media_download import store_bytes
from app.connectors.oss.common import (
    content_type_for,
    pick_media_file,
    username_from_target,
)
from app.connectors.session_cookies import cookies_from_sessions
from app.date_window import DateWindow
from app.objectstore import ObjectStore

logger = logging.getLogger(__name__)


class InstaloaderError(RuntimeError):
    pass


def fail_fast_rate_controller(context: Any) -> Any:
    """Refuse Instaloader's 11-minute 429 sleeps so OSS can fall back to browser."""
    import instaloader

    class _FailFast(instaloader.RateController):
        def sleep(self, secs: float) -> None:
            if secs > 5:
                raise InstaloaderError(
                    f"instagram asked to wait {secs:.0f}s — falling back to browser"
                )
            super().sleep(min(float(secs), 1.0))

    return _FailFast(context)


@dataclass
class _Draft:
    post: RawPost
    media_path: Path | None


def _apply_cookies(loader: Any, cookies: list[dict[str, Any]]) -> None:
    jar = loader.context._session.cookies
    for c in cookies:
        name = str(c.get("name") or "")
        if not name:
            continue
        domain = str(c.get("domain") or ".instagram.com")
        path = str(c.get("path") or "/")
        jar.set(name, str(c["value"]), domain=domain, path=path)


async def fetch_instagram_instaloader(
    *,
    run_id: str,
    handle: str,
    url: str,
    window: DateWindow,
    platform_sessions: dict[str, Any],
    object_store: ObjectStore | None,
    max_posts: int = 40,
) -> tuple[RawAccount, list[RawPost]]:
    cookies = cookies_from_sessions(platform_sessions, platforms={"instagram"})
    if not cookies:
        raise InstaloaderError("no instagram connect cookies")

    with tempfile.TemporaryDirectory(prefix="rr-ig-") as tmp:
        account, drafts = await asyncio.to_thread(
            _fetch_sync,
            handle=handle,
            url=url,
            window=window,
            cookies=cookies,
            out_dir=Path(tmp),
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
    try:
        import instaloader
    except ImportError as exc:  # pragma: no cover
        raise InstaloaderError("instaloader not installed") from exc

    username = username_from_target(handle, url)

    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=True,
        compress_json=False,
        post_metadata_txt_pattern="",
        max_connection_attempts=1,
        quiet=True,
        rate_controller=fail_fast_rate_controller,
    )
    _apply_cookies(L, cookies)
    L.dirname_pattern = str(out_dir / "{target}")
    L.filename_pattern = "{date_utc}_UTC_{shortcode}"

    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except Exception as exc:  # noqa: BLE001
        raise InstaloaderError(f"profile load failed @{username}: {exc}") from exc

    account = RawAccount(
        handle=f"@{profile.username}"[:100],
        display_name=(profile.full_name or profile.username)[:200],
        platform="instagram",
    )

    drafts: list[_Draft] = []
    for post in profile.get_posts():
        if len(drafts) >= max_posts:
            break
        posted = post.date_utc.replace(tzinfo=UTC)
        if posted.date() < window.date_from:
            break
        if not window.contains(posted):
            continue

        shortcode = post.shortcode
        try:
            L.download_post(post, target=username)
        except Exception as exc:  # noqa: BLE001
            logger.warning("instaloader download_post %s: %s", shortcode, exc)

        media_path = pick_media_file(out_dir, stem_hints=[shortcode])
        post_url = f"https://www.instagram.com/p/{shortcode}/"
        remote = post.url
        raw = RawPost(
            account_handle=account["handle"],
            external_post_id=f"instagram:{shortcode}"[:100],
            format="reel" if post.is_video else "founder_post",
            theme_tags=[
                "instagram",
                "source:instaloader",
                f"link:{post_url}",
                f"date_from:{window.date_from.isoformat()}",
                f"date_to:{window.date_to.isoformat()}",
            ],
            caption=(post.caption or "")[:2000] or f"Instagram @{username}",
            image_url=remote,
            likes=int(post.likes or 0),
            comments=int(post.comments or 0),
            shares=0,
            views=int(getattr(post, "video_view_count", None) or 0),
            posted_at=posted.isoformat().replace("+00:00", "Z"),
            media_urls=[remote] if remote else [],
            media_keys=[],
        )
        drafts.append(_Draft(post=raw, media_path=media_path))

    return account, drafts
