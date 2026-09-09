import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


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
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    account: Mapped[CompetitorAccount] = relationship(back_populates="posts")

    @property
    def engagement_score(self) -> int:
        return self.likes + self.comments * 3 + self.shares * 5

    @property
    def themes(self) -> list[str]:
        return [t.strip() for t in self.theme_tags.split(",") if t.strip()]
