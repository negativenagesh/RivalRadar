from typing import NotRequired, Protocol, TypedDict


class RawAccount(TypedDict):
    handle: str
    display_name: str
    platform: str


class CommentSample(TypedDict):
    author: str
    text: str
    likes: int


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
    views: NotRequired[int]
    media_urls: NotRequired[list[str]]
    media_keys: NotRequired[list[str]]
    comment_sample: NotRequired[list[CommentSample]]


class Connector(Protocol):
    """Source of competitor account/post data.

    A real scraper or paid-API integration implements this same interface
    later; the rest of the ingestion service never needs to change.
    """

    async def fetch_accounts(self) -> list[RawAccount]: ...

    async def fetch_posts(self) -> list[RawPost]: ...
