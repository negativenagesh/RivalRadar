from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.date_window import DateWindow, DateWindowError
from app.models import PostFormat, RunStatus


class CommentSampleRead(BaseModel):
    author: str
    text: str
    likes: int = 0


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
    views: int = 0
    media_urls: list[str] = Field(default_factory=list)
    media_keys: list[str] = Field(default_factory=list)
    comment_sample: list[CommentSampleRead] = Field(default_factory=list)
    posted_at: datetime
    engagement_score: int
    themes: list[str]


class IngestionRunResult(BaseModel):
    accounts_ingested: int
    posts_ingested: int
    posts_skipped_duplicate: int
    lookback_days: int | None = None
    date_from: str | None = None
    date_to: str | None = None
    sources_used: list[str] = Field(default_factory=list)


class ProfileTargetIn(BaseModel):
    handle: str
    platform: str = "mock"
    url: str | None = None


class IngestionRunCreate(BaseModel):
    connector: Literal["fixture", "social_profile", "youtube", "auto"] = "fixture"
    targets: list[ProfileTargetIn] = []
    record: bool = False
    headless: bool = True
    lookback_days: int = Field(default=3, ge=1, le=90)
    date_from: date | None = None
    date_to: date | None = None
    # Decrypted Connect Center sessions keyed by platform (linkedin, x, …)
    platform_sessions: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_window(self) -> "IngestionRunCreate":
        try:
            DateWindow.resolve(
                lookback_days=self.lookback_days,
                date_from=self.date_from,
                date_to=self.date_to,
            )
        except DateWindowError as exc:
            raise ValueError(str(exc)) from exc
        return self

    def resolved_window(self) -> DateWindow:
        return DateWindow.resolve(
            lookback_days=self.lookback_days,
            date_from=self.date_from,
            date_to=self.date_to,
        )


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
    result: dict[str, Any] | None
    created_at: datetime


class YoutubeStatusRead(BaseModel):
    api_key_configured: bool
    preferred_source: Literal["youtube_api", "yt_dlp"]


class SocialCommentRequest(BaseModel):
    platform: str
    url: str
    text: str
    approved: bool = False
    platform_sessions: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SocialCommentResult(BaseModel):
    ok: bool
    detail: str
    screenshot_jpeg_b64: str | None = None
