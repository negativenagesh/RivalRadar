import pytest
from app.main import app
from app.routes import operator_provider
from httpx import ASGITransport, AsyncClient

from llm_provider import LLMProviderError, get_llm_provider, provider_from_operator
from tests.fakes import FakeLLMProvider


async def test_mission_llm_requires_a_text_key(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GEMINI_API_KEY", "DEEPSEEK_API_KEY", "NVIDIA_API_KEY", "AGNES_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    app.dependency_overrides.pop(operator_provider, None)
    app.dependency_overrides.pop(get_llm_provider, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creative = await client.post(
            "/creative/generate",
            json={"kind": "comment", "brand_name": "Pixis"},
        )
        assert creative.status_code == 400
        assert "Models chip" in creative.json()["detail"] or "key" in creative.json()["detail"]

        intel = await client.post("/intel/report", json={"facts": {}, "brand_name": "Pixis"})
        assert intel.status_code == 400
        assert "Models chip" in intel.json()["detail"] or "key" in intel.json()["detail"]


async def test_mission_defaults_to_gptoss_and_agnes_from_server_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No operator keys + server env keys → default text=gpt-oss, image=Agnes."""
    from llm_provider.factory import server_model_defaults
    from llm_provider.routing import RoutingLLMProvider

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-server")
    monkeypatch.setenv("AGNES_API_KEY", "agnes-server")

    defaults = server_model_defaults()
    assert defaults["text_model"] == "gptoss"
    assert defaults["image_model"] == "agnes"
    assert defaults["available"] is True

    provider = provider_from_operator()
    assert isinstance(provider, RoutingLLMProvider)
    from llm_provider.agnes import AgnesImageProvider
    from llm_provider.nvidia import NvidiaGptOssProvider

    assert isinstance(provider._text, NvidiaGptOssProvider)
    assert isinstance(provider._image, AgnesImageProvider)


async def test_server_defaults_fall_back_to_gemini_without_nvidia_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from llm_provider.factory import server_model_defaults

    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gm-server")

    defaults = server_model_defaults()
    assert defaults["text_model"] == "gemini"
    assert defaults["image_model"] == "nano_banana"


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
