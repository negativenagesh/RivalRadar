from fastapi import APIRouter, Depends

from app.check import run_compliance_check
from app.schemas import ComplianceCheckRequest, ComplianceCheckResponse
from llm_provider import LLMProvider, get_llm_provider

router = APIRouter()


@router.post("/compliance/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    request: ComplianceCheckRequest,
    provider: LLMProvider = Depends(get_llm_provider),
) -> ComplianceCheckResponse:
    return await run_compliance_check(request.text, provider)
