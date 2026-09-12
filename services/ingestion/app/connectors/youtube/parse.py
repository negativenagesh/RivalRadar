"""Parse YouTube channel URLs into a resolvable handle / channel id hint."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class YouTubeRef:
    """Normalized channel reference from a user-pasted URL or @handle."""

    handle: str  # display handle without leading @ when possible
    channel_id: str | None = None
    url: str | None = None


_CHANNEL_ID = re.compile(r"youtube\.com/channel/(UC[\w-]{22})", re.I)
_AT_HANDLE = re.compile(r"youtube\.com/@([\w.-]+)", re.I)
_CUSTOM = re.compile(r"youtube\.com/(?:c|user)/([\w.-]+)", re.I)
_BARE_AT = re.compile(r"^@?([\w.-]+)$")


def parse_youtube_ref(raw: str) -> YouTubeRef | None:
    text = raw.strip()
    if not text:
        return None

    if not text.startswith("http"):
        text_url = f"https://www.youtube.com/{text.lstrip('/')}"
    else:
        text_url = text

    m = _CHANNEL_ID.search(text_url)
    if m:
        cid = m.group(1)
        return YouTubeRef(handle=cid, channel_id=cid, url=text_url)

    m = _AT_HANDLE.search(text_url)
    if m:
        handle = m.group(1)
        return YouTubeRef(handle=handle, url=text_url)

    m = _CUSTOM.search(text_url)
    if m:
        handle = m.group(1)
        return YouTubeRef(handle=handle, url=text_url)

    m = _BARE_AT.match(raw.strip())
    if m:
        handle = m.group(1)
        return YouTubeRef(handle=handle, url=f"https://www.youtube.com/@{handle}")

    return None
