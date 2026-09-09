from typing import Protocol, TypedDict


class RawAccount(TypedDict):
    handle: str
    display_name: str
    platform: str


class RawPost(TypedDict):
    account_handle: str
    external_post_id: str
    format: str
    theme_tags: list[str]
    caption: str
    image_url: str | None
    likes: int
    comments: int
    shares: int
    posted_at: str


class Connector(Protocol):
    """Source of competitor account/post data.

    A real scraper or paid-API integration implements this same interface
    later; the rest of the ingestion service never needs to change.
    """

    async def fetch_accounts(self) -> list[RawAccount]: ...

    async def fetch_posts(self) -> list[RawPost]: ...
