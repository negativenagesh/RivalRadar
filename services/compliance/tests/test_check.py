from app.check import run_compliance_check

from tests.fakes import FakeLLMProvider


async def test_passes_when_both_checks_pass() -> None:
    provider = FakeLLMProvider(completion='{"safe": true, "reason": ""}')

    result = await run_compliance_check("a clean on-brand caption", provider)

    assert result.passed is True
    assert result.rule_violations == []
    assert result.llm_safe is True


async def test_fails_when_rule_check_fails_even_if_llm_says_safe() -> None:
    provider = FakeLLMProvider(completion='{"safe": true, "reason": ""}')

    result = await run_compliance_check("guaranteed results, act now!!!", provider)

    assert result.passed is False
    assert len(result.rule_violations) > 0


async def test_fails_when_llm_says_unsafe_even_if_rules_pass() -> None:
    provider = FakeLLMProvider(completion='{"safe": false, "reason": "too close to a competitor ad"}')

    result = await run_compliance_check("a clean-sounding but risky caption", provider)

    assert result.passed is False
    assert result.rule_violations == []
    assert result.llm_reason == "too close to a competitor ad"
