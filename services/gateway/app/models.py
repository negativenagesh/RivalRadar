import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class ReviewState(enum.StrEnum):
    PENDING = "pending"
    EDITED = "edited"
    REJECTED = "rejected"
    READY_TO_PUBLISH = "ready_to_publish"


class PipelineRunStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class PipelineRun(Base):
    """Tracks one draft-generation pipeline run (digest -> generate ->
    compliance, per cluster) so its live progress is addressable by id."""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[PipelineRunStatus] = mapped_column(String(30), default=PipelineRunStatus.PENDING)
    digest_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    draft_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Draft(Base):
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    digest_id: Mapped[str] = mapped_column(String(36), index=True)
    cluster_format: Mapped[str] = mapped_column(String(50))
    cluster_theme: Mapped[str] = mapped_column(String(100))
    caption: Mapped[str] = mapped_column(Text)
    image_concept: Mapped[str] = mapped_column(Text)
    image_mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_data_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    voice_examples_used: Mapped[list[str]] = mapped_column(JSON)
    compliance_passed: Mapped[bool]
    compliance_rule_violations: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    compliance_llm_reason: Mapped[str] = mapped_column(Text)
    review_state: Mapped[ReviewState] = mapped_column(
        String(30), default=ReviewState.PENDING
    )
    edited_caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    @property
    def final_caption(self) -> str:
        return self.edited_caption if self.edited_caption is not None else self.caption
