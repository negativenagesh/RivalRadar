from llm_provider.base import LLMProviderError
from llm_provider.gemini import translate_openai_error


class _StatusError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def test_translate_429_asks_operator_to_wait() -> None:
    err = translate_openai_error(
        _StatusError(
            429,
            "Error code: 429 - Quota exceeded. Please retry in 35.570461437s.",
        )
    )
    assert isinstance(err, LLMProviderError)
    assert err.status_code == 429
    assert err.retry_after == 35
    assert "5 text requests" in err.detail
    assert "35s" in err.detail


def test_translate_401_points_at_operator_key() -> None:
    err = translate_openai_error(_StatusError(401, "invalid api key"))
    assert err.status_code == 401
    assert "API key" in err.detail
