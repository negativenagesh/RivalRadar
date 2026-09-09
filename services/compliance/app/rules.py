import re

from pydantic import BaseModel

BANNED_CLAIM_PATTERNS: dict[str, str] = {
    r"\bcures?\b": "unsubstantiated medical claim ('cure')",
    r"\bguaranteed?\s+results?\b": "unsubstantiated outcome guarantee",
    r"\b100%\s*(safe|effective|guaranteed)\b": "absolute claim with no room for caveats",
    r"\bbest\s+in\s+the\s+world\b": "unsubstantiated superiority claim",
    r"\bno\s+side\s+effects?\b": "unsubstantiated safety claim",
    r"\bdoctor[s]?\s+recommend(ed)?\b": "implied medical endorsement without substantiation",
    r"\bclinically\s+proven\b": "clinical claim without cited substantiation",
}

OFF_BRAND_TONE_PATTERNS: dict[str, str] = {
    r"[!?]{3,}": "excessive punctuation (off-brand shouty tone)",
    r"\b[A-Z]{5,}\b": "all-caps shouting",
    r"\bact\s+now\b": "high-pressure sales language",
    r"\blimited\s+time\s+only\b": "high-pressure urgency language",
}


class RuleViolation(BaseModel):
    rule: str
    category: str
    matched_text: str


class RuleCheckResult(BaseModel):
    passed: bool
    violations: list[RuleViolation]


def run_rule_checks(text: str) -> RuleCheckResult:
    """Deterministic, zero-LLM-call pattern checks.

    Runs first because it's free, instant, and catches the clearest cases
    (banned claims, shouty tone) without spending an LLM call on them. The
    LLM classifier pass (app/classifier.py) handles nuance this can't:
    tone/sentiment judgment calls that aren't reducible to a regex.
    """
    violations: list[RuleViolation] = []

    for pattern, description in BANNED_CLAIM_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            violations.append(
                RuleViolation(rule=description, category="banned_claim", matched_text=match.group(0))
            )

    for pattern, description in OFF_BRAND_TONE_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            violations.append(
                RuleViolation(rule=description, category="tone", matched_text=match.group(0))
            )

    return RuleCheckResult(passed=len(violations) == 0, violations=violations)
