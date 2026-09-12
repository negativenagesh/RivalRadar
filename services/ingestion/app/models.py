import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class RunStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class PostFormat(enum.StrEnum):
    MEME = "meme"
    PRODUCT_LAUNCH_CAROUSEL = "product_launch_carousel"
    FOUNDER_POST = "founder_post"
    UGC_REPOST = "ugc_repost"


class CompetitorAccount(Base):
    __tablename__ = "competitor_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    handle: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    posts: Mapped[list["CompetitorPost"]] = relationship(back_populates="account")


class CompetitorPost(Base):
    __tablename__ = "competitor_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[str] = mapped_column(ForeignKey("competitor_accounts.id"), index=True)
    external_post_id: Mapped[str] = mapped_column(String(100), unique=True)
    format: Mapped[PostFormat] = mapped_column(Enum(PostFormat))
    theme_tags: Mapped[str] = mapped_column(String(300))
    caption: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    media_urls: Mapped[list[str]] = mapped_column(JSON, default=list)
    media_keys: Mapped[list[str]] = mapped_column(JSON, default=list)
    comment_sample: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    account: Mapped[CompetitorAccount] = relationship(back_populates="posts")

    @property
    def engagement_score(self) -> int:
        # views weighted lightly so YouTube heat stays useful without stuffing views into shares
        return self.likes + self.comments * 3 + self.shares * 5 + max(0, self.views // 100)

    @property
    def themes(self) -> list[str]:
        return [t.strip() for t in self.theme_tags.split(",") if t.strip()]


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    connector_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.PENDING)
    record: Mapped[bool] = mapped_column(default=False)
    recording_key: Mapped[str | None] = mapped_column(String(300), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
