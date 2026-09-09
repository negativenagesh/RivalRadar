from typing import TypedDict

import httpx

from app.config import settings


class IngestedPost(TypedDict):
    id: str
    account_id: str
    external_post_id: str
    format: str
    theme_tags: str
    caption: str
    image_url: str | None
    likes: int
    comments: int
    shares: int
    posted_at: str
    engagement_score: int
    themes: list[str]


async def fetch_posts() -> list[IngestedPost]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=10.0) as client:
        response = await client.get("/posts")
        response.raise_for_status()
        posts: list[IngestedPost] = response.json()
        return posts
