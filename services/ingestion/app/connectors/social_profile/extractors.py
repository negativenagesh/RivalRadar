"""Pure functions turning already-extracted DOM field dicts into the
Connector's RawAccount/RawPost shapes. Kept free of Playwright calls so
they're unit-testable against plain dicts, independent of a live browser.
"""

from __future__ import annotations

from app.connectors.base import RawAccount, RawPost


def build_raw_account(*, handle: str, display_name: str, platform: str) -> RawAccount:
    return RawAccount(handle=handle, display_name=display_name, platform=platform)


def build_raw_post(
    *,
    account_handle: str,
    external_post_id: str,
    format: str,
    theme_tags_csv: str,
    caption: str,
    image_url: str | None,
    likes: str,
    comments: str,
    shares: str,
    posted_at: str,
) -> RawPost:
    return RawPost(
        account_handle=account_handle,
        external_post_id=external_post_id,
        format=format,
        theme_tags=[t.strip() for t in theme_tags_csv.split(",") if t.strip()],
        caption=caption,
        image_url=image_url,
        likes=int(likes),
        comments=int(comments),
        shares=int(shares),
        posted_at=posted_at,
    )
