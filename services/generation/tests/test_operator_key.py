from app.main import app
from app.routes import operator_provider
from httpx import ASGITransport, AsyncClient

from llm_provider import LLMProviderError, get_llm_provider
from tests.fakes import FakeLLMProvider


async def test_mission_llm_requires_a_text_key() -> None:
    app.dependency_overrides.pop(operator_provider, None)
    app.dependency_overrides.pop(get_llm_provider, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creative = await client.post(
            "/creative/generate",
            json={"kind": "comment", "brand_name": "Pixis"},
        )
        assert creative.status_code == 400
        assert "Models chip" in creative.json()["detail"] or "Gemini" in creative.json()["detail"]

        intel = await client.post("/intel/report", json={"facts": {}, "brand_name": "Pixis"})
        assert intel.status_code == 400
        assert "Models chip" in intel.json()["detail"] or "Gemini" in intel.json()["detail"]


async def test_creative_accepts_deepseek_operator_key() -> None:
    fake = FakeLLMProvider(completion="deep take")
    app.dependency_overrides[operator_provider] = lambda: fake
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/creative/generate",
                json={"kind": "comment", "brand_name": "Pixis"},
                headers={
                    "X-DeepSeek-Key": "sk-operator",
                    "X-Agnes-Key": "sk-agnes-operator",
                    "X-Text-Model": "deepseek",
                    "X-Image-Model": "agnes",
                },
            )
    finally:
        app.dependency_overrides.pop(operator_provider, None)
    assert response.status_code == 200
    assert "take" in response.json()["text"]


class _RateLimitFake(FakeLLMProvider):
    async def complete(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        raise LLMProviderError(
            "Gemini rate limit — free tier allows 5 text requests/minute on this model. Wait ~35s and Generate again.",
            status_code=429,
            retry_after=35,
        )


async def test_creative_rate_limit_is_429_not_500() -> None:
    app.dependency_overrides[operator_provider] = lambda: _RateLimitFake()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/creative/generate",
                json={"kind": "studio", "brand_name": "Pixis", "format": "hot_take"},
                headers={"X-Gemini-Key": "AIza-operator"},
            )
    finally:
        app.dependency_overrides.pop(operator_provider, None)
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()
    assert response.headers.get("retry-after") == "35"
