from pydantic import BaseModel

from app.rules import RuleViolation


class ComplianceCheckRequest(BaseModel):
    text: str


class ComplianceCheckResponse(BaseModel):
    passed: bool
    rule_violations: list[RuleViolation]
    llm_safe: bool
    llm_reason: str
