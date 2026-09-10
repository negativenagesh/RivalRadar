from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import PostFormat, RunStatus


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


class ProfileTargetIn(BaseModel):
    handle: str
    platform: str = "mock"
    url: str | None = None


class IngestionRunCreate(BaseModel):
    connector: Literal["fixture", "social_profile"] = "fixture"
    targets: list[ProfileTargetIn] = []
    record: bool = False
    headless: bool = True


class IngestionRunCreated(BaseModel):
    run_id: str
    status: RunStatus


class IngestionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    connector_type: str
    status: RunStatus
    record: bool
    recording_key: str | None
    error_detail: str | None
    result: dict[str, object] | None
    created_at: datetime
