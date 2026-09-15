import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.creative import CreativeRequest, CreativeResponse, generate_creative
from app.drafting import draft_response
from app.intel import IntelReport, IntelRequest, generate_intel, generate_intel_events
from app.publish import PublishPlanRequest, PublishPlanResponse, generate_publish_plan
from app.schemas import DraftRequest, DraftResponse
from app.voice.retrieval import load_corpus
from llm_provider import (
    LLMProvider,
    LLMProviderError,
    get_llm_provider,
    ping_vendor,
    provider_from_operator,
    server_model_defaults,
)

router = APIRouter()

KEYS_MISSING = (
    "Paste a key in the Models chip, or set NVIDIA_API_KEY / AGNES_API_KEY / "
    "GEMINI_API_KEY in the server .env (defaults: gpt-oss text, Agnes image)."
)


class PingRequest(BaseModel):
    vendor: str = Field(min_length=3, max_length=20)


def operator_provider(
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
    x_text_model: str | None = Header(default=None, alias="X-Text-Model"),
    x_image_model: str | None = Header(default=None, alias="X-Image-Model"),
) -> LLMProvider:
    try:
        return provider_from_operator(
            gemini_key=x_gemini_key,
            deepseek_key=x_deepseek_key,
            nvidia_key=x_nvidia_key,
            agnes_key=x_agnes_key,
            text_model=x_text_model,
            image_model=x_image_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc) or KEYS_MISSING) from exc


def _llm_http(exc: LLMProviderError) -> HTTPException:
    headers: dict[str, str] | None = (
        {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    )
    return HTTPException(status_code=exc.status_code, detail=exc.detail, headers=headers)


@router.get("/models/defaults")
async def model_defaults() -> dict[str, object]:
    """Which Mission models the server can drive from env keys alone."""
    defaults: dict[str, object] = server_model_defaults()
    return defaults


@router.post("/drafts/generate", response_model=DraftResponse)
async def generate_draft(
    request: DraftRequest,
    provider: LLMProvider = Depends(get_llm_provider),
) -> DraftResponse:
    corpus = load_corpus()
    return await draft_response(request, corpus, provider)


@router.post("/llm/ping")
async def llm_ping(
    request: PingRequest,
    x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_deepseek_key: str | None = Header(default=None, alias="X-DeepSeek-Key"),
    x_nvidia_key: str | None = Header(default=None, alias="X-Nvidia-Key"),
    x_agnes_key: str | None = Header(default=None, alias="X-Agnes-Key"),
) -> dict[str, str]:
    vendor = request.vendor.strip().lower()
    key = {
        "gemini": x_gemini_key,
        "deepseek": x_deepseek_key,
        "nvidia": x_nvidia_key,
        "agnes": x_agnes_key,
    }.get(vendor)
    if not (key or "").strip():
        raise HTTPException(status_code=400, detail=f"Paste your {vendor} API key to test it.")
    try:
        payload: dict[str, str] = await ping_vendor(vendor, key or "")
        return payload
    except LLMProviderError as exc:
        raise _llm_http(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/creative/generate", response_model=CreativeResponse)
async def creative_generate(
    request: CreativeRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> CreativeResponse:
    try:
        return await generate_creative(request, provider)
    except LLMProviderError as exc:
        raise _llm_http(exc) from exc


@router.post("/creative/publish-plan", response_model=PublishPlanResponse)
async def creative_publish_plan(
    request: PublishPlanRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> PublishPlanResponse:
    try:
        return await generate_publish_plan(request, provider)
    except LLMProviderError as exc:
        raise _llm_http(exc) from exc


@router.post("/intel/report", response_model=IntelReport)
async def intel_report(
    request: IntelRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> IntelReport:
    try:
        return await generate_intel(request, provider)
    except LLMProviderError as exc:
        raise _llm_http(exc) from exc


@router.post("/intel/report/stream")
async def intel_report_stream(
    request: IntelRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> StreamingResponse:
    """SSE: stage/agent progress events, then the final merged IntelReport."""

    async def events() -> AsyncIterator[str]:
        try:
            async for payload in generate_intel_events(request, provider):
                event = str(payload.pop("event"))
                yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        except LLMProviderError as exc:
            detail = json.dumps({"detail": exc.detail}, ensure_ascii=False)
            yield f"event: error\ndata: {detail}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
