from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import PipelineRunStatus, ReviewState


class DraftRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    digest_id: str
    cluster_format: str
    cluster_theme: str
    caption: str
    image_concept: str
    image_mime_type: str | None
    image_data_base64: str | None
    voice_examples_used: list[str]
    compliance_passed: bool
    compliance_rule_violations: list[dict[str, object]]
    compliance_llm_reason: str
    review_state: ReviewState
    edited_caption: str | None
    final_caption: str
    created_at: datetime
    updated_at: datetime


class EditRequest(BaseModel):
    caption: str


class PipelineRunCreated(BaseModel):
    run_id: str
    status: PipelineRunStatus


class PipelineRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: PipelineRunStatus
    digest_id: str | None
    draft_ids: list[str]
    error_detail: str | None
    created_at: datetime
