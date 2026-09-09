from app.classifier import run_llm_classifier

from tests.fakes import FakeLLMProvider


async def test_classifier_parses_safe_response() -> None:
    provider = FakeLLMProvider(completion='{"safe": true, "reason": ""}')

    result = await run_llm_classifier("a nice on-brand caption", provider)

    assert result.safe is True
    assert result.reason == ""


async def test_classifier_parses_unsafe_response() -> None:
    provider = FakeLLMProvider(completion='{"safe": false, "reason": "mimics a competitor slogan"}')

    result = await run_llm_classifier("some risky caption", provider)

    assert result.safe is False
    assert result.reason == "mimics a competitor slogan"


async def test_classifier_handles_markdown_code_fence() -> None:
    provider = FakeLLMProvider(completion='```json\n{"safe": true, "reason": ""}\n```')

    result = await run_llm_classifier("a caption", provider)

    assert result.safe is True


async def test_classifier_fails_closed_on_unparseable_response() -> None:
    provider = FakeLLMProvider(completion="not json at all")

    result = await run_llm_classifier("a caption", provider)

    assert result.safe is False
    assert "unparseable" in result.reason
