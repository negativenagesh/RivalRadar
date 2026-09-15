from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


async def test_creative_and_intel_forward_empty_headers_for_server_env(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No operator keys → gateway forwards anyway; generation falls back to server env keys."""
    mock = AsyncMock(return_value={"kind": "comment", "text": "server env"})
    monkeypatch.setattr("app.routes.generate_creative_content", mock)
    creative = await client.post("/creative/generate", json={"kind": "comment", "brand_name": "Pixis"})
    assert creative.status_code == 200
    assert mock.await_args is not None
    assert mock.await_args.kwargs["operator_headers"] == {}


async def test_creative_forwards_operator_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value={"kind": "comment", "text": "dry take"})
    monkeypatch.setattr("app.routes.generate_creative_content", mock)
    response = await client.post(
        "/creative/generate",
        json={"kind": "comment", "brand_name": "Pixis"},
        headers={"X-Gemini-Key": "AIza-operator"},
    )
    assert response.status_code == 200
    mock.assert_awaited_once()
    called = mock.await_args
    assert called is not None
    assert called.kwargs["operator_headers"]["X-Gemini-Key"] == "AIza-operator"


async def test_creative_forwards_deepseek_and_nvidia_headers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value={"kind": "studio", "text": "caption"})
    monkeypatch.setattr("app.routes.generate_creative_content", mock)
    response = await client.post(
        "/creative/generate",
        json={"kind": "studio", "brand_name": "Pixis"},
        headers={
            "X-DeepSeek-Key": "sk-operator",
            "X-Nvidia-Key": "nv-operator",
            "X-Agnes-Key": "sk-agnes-operator",
            "X-Text-Model": "deepseek",
            "X-Image-Model": "agnes",
        },
    )
    assert response.status_code == 200
    called = mock.await_args
    assert called is not None
    headers = called.kwargs["operator_headers"]
    assert headers["X-DeepSeek-Key"] == "sk-operator"
    assert headers["X-Nvidia-Key"] == "nv-operator"
    assert headers["X-Agnes-Key"] == "sk-agnes-operator"
    assert headers["X-Text-Model"] == "deepseek"
    assert headers["X-Image-Model"] == "agnes"


async def test_intel_forwards_operator_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value={"scoreboard_blurb": "live", "markdown": "# Intel brief"})
    monkeypatch.setattr("app.routes.generate_intel_report", mock)
    response = await client.post(
        "/intel/report",
        json={"facts": {}, "brand_name": "Pixis"},
        headers={"X-Gemini-Key": "AIza-operator"},
    )
    assert response.status_code == 200
    mock.assert_awaited_once()
    called = mock.await_args
    assert called is not None
    assert called.kwargs["operator_headers"]["X-Gemini-Key"] == "AIza-operator"


async def test_publish_plan_forwards_operator_headers(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value={"platform": "linkedin", "variations": []})
    monkeypatch.setattr("app.routes.generate_publish_plan", mock)
    response = await client.post(
        "/creative/publish-plan",
        json={"brand_name": "Pixis", "platform": "linkedin", "asset_caption": "roast"},
        headers={"X-Text-Model": "gptoss"},
    )
    assert response.status_code == 200
    called = mock.await_args
    assert called is not None
    assert called.kwargs["operator_headers"]["X-Text-Model"] == "gptoss"


async def test_social_stage_post_requires_approval(client: AsyncClient) -> None:
    response = await client.post(
        "/social/stage-post",
        json={"platform": "x", "caption": "ship it", "approved": False},
    )
    assert response.status_code == 400
    assert "approval" in response.json()["detail"]


async def test_social_stage_post_requires_connection(client: AsyncClient) -> None:
    response = await client.post(
        "/social/stage-post",
        json={"platform": "x", "caption": "ship it", "approved": True},
    )
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"]


async def test_social_comment_requires_approval(client: AsyncClient) -> None:
    response = await client.post(
        "/social/comment",
        json={
            "platform": "linkedin",
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:1",
            "text": "sharp take",
            "approved": False,
        },
    )
    assert response.status_code == 400
    assert "approval" in response.json()["detail"]


async def test_social_comment_requires_connection(client: AsyncClient) -> None:
    response = await client.post(
        "/social/comment",
        json={
            "platform": "linkedin",
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:1",
            "text": "sharp take",
            "approved": True,
        },
    )
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"]
