from fastapi import APIRouter, Depends

from app.drafting import draft_response
from app.schemas import DraftRequest, DraftResponse
from app.voice.retrieval import load_corpus
from llm_provider import LLMProvider, get_llm_provider

router = APIRouter()


@router.post("/drafts/generate", response_model=DraftResponse)
async def generate_draft(
    request: DraftRequest,
    provider: LLMProvider = Depends(get_llm_provider),
) -> DraftResponse:
    corpus = load_corpus()
    return await draft_response(request, corpus, provider)
