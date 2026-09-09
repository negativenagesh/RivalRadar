from app.classifier import run_llm_classifier
from app.rules import run_rule_checks
from app.schemas import ComplianceCheckResponse
from llm_provider import LLMProvider


async def run_compliance_check(text: str, provider: LLMProvider) -> ComplianceCheckResponse:
    rule_result = run_rule_checks(text)
    classifier_result = await run_llm_classifier(text, provider)

    return ComplianceCheckResponse(
        passed=rule_result.passed and classifier_result.safe,
        rule_violations=rule_result.violations,
        llm_safe=classifier_result.safe,
        llm_reason=classifier_result.reason,
    )
