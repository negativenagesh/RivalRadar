"""Shared helpers for OSS platform scrapers."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.date_window import DateWindow


def handle_from_url(url: str, *, fallback: str = "@unknown") -> str:
    path = urlparse(url).path.strip("/")
    part = path.split("/")[0] if path else ""
    if part.startswith("@"):
        part = part[1:]
    if part in {"company", "in", "school"} and len(path.split("/")) > 1:
        part = path.split("/")[1]
    raw = re.sub(r"[^\w.-]+", ".", part or fallback.lstrip("@"))[:80]
    return f"@{raw}" if not raw.startswith("@") else raw


def username_from_target(handle: str, url: str) -> str:
    h = (handle or "").strip().lstrip("@")
    if h and " " not in h and "/" not in h:
        return h
    return handle_from_url(url).lstrip("@")


def ytdlp_yyyymmdd(d: date) -> str:
    return d.strftime("%Y%m%d")


def gallery_dl_date(d: date) -> str:
    return d.isoformat()


def instaloader_post_filter(window: DateWindow) -> str:
    """Exclusive upper bound = day after date_to."""
    end = window.date_to + timedelta(days=1)
    a, b = window.date_from, end
    return (
        f"date_utc >= datetime({a.year}, {a.month}, {a.day}) and "
        f"date_utc < datetime({b.year}, {b.month}, {b.day})"
    )


def parse_posted_at(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, (int, float)):
        from datetime import UTC

        return datetime.fromtimestamp(float(raw), tz=UTC)
    if isinstance(raw, str):
        text = raw.strip().replace("Z", "+00:00")
        # YYYYMMDD
        if re.fullmatch(r"\d{8}", text):
            from datetime import UTC

            return datetime(
                int(text[0:4]), int(text[4:6]), int(text[6:8]), tzinfo=UTC
            )
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


def pick_media_file(folder: Path, stem_hints: list[str] | None = None) -> Path | None:
    if not folder.exists():
        return None
    preferred = {".mp4", ".webm", ".mov", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in preferred]
    if not files:
        return None
    if stem_hints:
        for hint in stem_hints:
            for p in files:
                if hint in p.stem:
                    return p
    # Prefer video over image
    videos = [p for p in files if p.suffix.lower() in {".mp4", ".webm", ".mov"}]
    if videos:
        return max(videos, key=lambda p: p.stat().st_size)
    return max(files, key=lambda p: p.stat().st_size)


def content_type_for(path: Path) -> str:
    return {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".mov": "video/quicktime",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(path.suffix.lower(), "application/octet-stream")
