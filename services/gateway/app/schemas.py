from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class ConnectionStatusRead(BaseModel):
    platform: str
    status: Literal["connected", "needs_reconnect", "not_connected"]
    auth_type: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    detail: str | None = None


class ConnectionUpsert(BaseModel):
    auth_type: Literal["oauth", "cookie", "api_key"] = "cookie"
    # Opaque secrets — tokens or cookie JSON. Never passwords.
    secret: dict[str, object] = Field(default_factory=dict)
    expires_at: datetime | None = None
    scopes: list[str] = Field(default_factory=list)
    workspace_id: str = "default"


class ConnectSessionStart(BaseModel):
    workspace_id: str = "default"


class ConnectSessionRead(BaseModel):
    session_id: str
    platform: str
    status: Literal["awaiting_login", "ready", "completed", "cancelled", "expired", "error"]
    login_url: str
    detail: str | None = None
    agent_online: bool = True
    viewer_url: str | None = None


class PairingCodeRequest(BaseModel):
    workspace_id: str = "default"


class PairingCodeRead(BaseModel):
    code: str
    expires_in: int
    workspace_id: str = "default"


class QuickConnectRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)
    cookies: list[dict[str, object]] = Field(default_factory=list, min_length=1)
    workspace_id: str = "default"
