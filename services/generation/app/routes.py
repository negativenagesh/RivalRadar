from fastapi import APIRouter, Depends, Header, HTTPException

from app.creative import CreativeRequest, CreativeResponse, generate_creative
from app.drafting import draft_response
from app.intel import IntelReport, IntelRequest, generate_intel
from app.schemas import DraftRequest, DraftResponse
from app.voice.retrieval import load_corpus
from llm_provider import LLMProvider, get_llm_provider, provider_from_key

router = APIRouter()


def operator_provider(x_gemini_key: str | None = Header(default=None, alias="X-Gemini-Key")) -> LLMProvider:
    key = (x_gemini_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400,
            detail="Paste your Gemini API key in Context or the navbar chip.",
        )
    try:
        return provider_from_key(key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/drafts/generate", response_model=DraftResponse)
async def generate_draft(
    request: DraftRequest,
    provider: LLMProvider = Depends(get_llm_provider),
) -> DraftResponse:
    corpus = load_corpus()
    return await draft_response(request, corpus, provider)


@router.post("/creative/generate", response_model=CreativeResponse)
async def creative_generate(
    request: CreativeRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> CreativeResponse:
    return await generate_creative(request, provider)


@router.post("/intel/report", response_model=IntelReport)
async def intel_report(
    request: IntelRequest,
    provider: LLMProvider = Depends(operator_provider),
) -> IntelReport:
    return await generate_intel(request, provider)
