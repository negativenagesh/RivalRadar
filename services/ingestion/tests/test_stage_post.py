from typing import Any

import pytest
from app.stage_post import StagePostError, stage_post, validate_stage
from httpx import AsyncClient


def test_stage_post_requires_human_approval() -> None:
    with pytest.raises(StagePostError, match="approval"):
        validate_stage(platform="linkedin", caption="shipping soon", approved=False)


def test_stage_post_accepts_youtube() -> None:
    assert validate_stage(platform="youtube", caption="Title\n\nDescription", approved=True) == "youtube"


def test_stage_post_rejects_empty_caption() -> None:
    with pytest.raises(StagePostError, match="empty"):
        validate_stage(platform="x", caption="  ", approved=True)


def test_stage_post_rejects_long_caption() -> None:
    with pytest.raises(StagePostError, match="too long"):
        validate_stage(platform="instagram", caption="x" * 3001, approved=True)


def test_stage_post_normalizes_twitter_to_x() -> None:
    assert validate_stage(platform="twitter", caption="hi", approved=True) == "x"


@pytest.mark.parametrize("platform", ["linkedin", "x", "instagram", "youtube"])
def test_stage_post_accepts_supported_platforms(platform: str) -> None:
    assert validate_stage(platform=platform, caption="launch notes", approved=True) == platform


async def test_stage_post_refuses_without_connection() -> None:
    with pytest.raises(StagePostError, match="not connected"):
        await stage_post(
            platform="linkedin",
            caption="hi",
            media_png_b64=None,
            approved=True,
            platform_sessions={},
        )


async def test_stage_post_route_requires_approval(client: AsyncClient) -> None:
    response = await client.post(
        "/social/stage-post",
        json={"platform": "linkedin", "caption": "hi", "approved": False},
    )
    assert response.status_code == 400
    assert "approval" in response.json()["detail"]


async def test_stage_post_route_returns_result(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    captured: dict[str, Any] = {}

    async def fake_stage_post(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return {
            "ok": True,
            "detail": "staged in linkedin composer",
            "screenshot_jpeg_b64": "aGVsbG8=",
        }

    monkeypatch.setattr("app.routes.stage_post", fake_stage_post)
    response = await client.post(
        "/social/stage-post",
        json={"platform": "linkedin", "caption": "hello world", "approved": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["detail"] == "staged in linkedin composer"
    assert body["screenshot_jpeg_b64"] == "aGVsbG8="
    assert captured["platform"] == "linkedin"
    assert captured["caption"] == "hello world"


async def test_stage_post_route_maps_stage_error(
    monkeypatch: pytest.MonkeyPatch, client: AsyncClient
) -> None:
    async def boom(**kwargs: Any) -> dict[str, Any]:
        raise StagePostError("not connected to x")

    monkeypatch.setattr("app.routes.stage_post", boom)
    response = await client.post(
        "/social/stage-post",
        json={"platform": "x", "caption": "hi", "approved": True},
    )
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"]
