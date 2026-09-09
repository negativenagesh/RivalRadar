import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    clusters: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    trending_themes: Mapped[list[str]] = mapped_column(JSON)
    gap_themes: Mapped[list[str]] = mapped_column(JSON)
    post_count: Mapped[int]
