from app.rules import run_rule_checks


def test_clean_caption_passes() -> None:
    result = run_rule_checks("New season, same rule: nothing goes into a Halo piece we wouldn't wear.")

    assert result.passed
    assert result.violations == []


def test_flags_unsubstantiated_medical_claim() -> None:
    result = run_rule_checks("This serum cures acne overnight!")

    assert not result.passed
    assert any(v.category == "banned_claim" for v in result.violations)


def test_flags_guaranteed_results_claim() -> None:
    result = run_rule_checks("Guaranteed results in 3 days or your money back.")

    assert not result.passed
    assert any("guarantee" in v.rule.lower() for v in result.violations)


def test_flags_absolute_percentage_claim() -> None:
    result = run_rule_checks("100% effective, no exceptions.")

    assert not result.passed


def test_flags_excessive_punctuation() -> None:
    result = run_rule_checks("BUY NOW!!!")

    assert not result.passed
    categories = {v.category for v in result.violations}
    assert "tone" in categories


def test_flags_high_pressure_urgency_language() -> None:
    result = run_rule_checks("Limited time only, act now before it's gone.")

    assert not result.passed
    reasons = [v.rule for v in result.violations]
    assert any("urgency" in r or "pressure" in r for r in reasons)


def test_multiple_violations_all_reported() -> None:
    result = run_rule_checks("GUARANTEED cure, ACT NOW!!!")

    assert not result.passed
    assert len(result.violations) >= 2
