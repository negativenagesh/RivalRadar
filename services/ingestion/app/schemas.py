from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import PostFormat


class CompetitorAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    handle: str
    display_name: str
    platform: str


class CompetitorPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_id: str
    external_post_id: str
    format: PostFormat
    theme_tags: str
    caption: str
    image_url: str | None
    likes: int
    comments: int
    shares: int
    posted_at: datetime
    engagement_score: int
    themes: list[str]


class IngestionRunResult(BaseModel):
    accounts_ingested: int
    posts_ingested: int
    posts_skipped_duplicate: int
