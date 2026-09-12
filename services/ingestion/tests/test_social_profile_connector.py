import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
import uvicorn
from app.connectors.social_profile import ProfileTarget, SocialProfileConnector
from app.mock_target_site.routes import router as mock_site_router
from fastapi import FastAPI


@pytest_asyncio.fixture
async def mock_site_base_url() -> AsyncGenerator[str]:
    """Serves just the mock-site router (no DB lifespan) on a real TCP
    port, since Playwright needs an actual HTTP server to navigate to --
    ASGI transport alone isn't reachable by a browser.
    """
    test_app = FastAPI()
    test_app.include_router(mock_site_router)

    config = uvicorn.Config(test_app, host="127.0.0.1", port=8999, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    async with asyncio.timeout(5):
        while not server.started:  # noqa: ASYNC110 -- polling uvicorn's readiness flag, not an Event
            await asyncio.sleep(0.05)

    yield "http://127.0.0.1:8999/mock-site/profile"

    server.should_exit = True
    await task


async def test_social_profile_connector_scrapes_mock_site(mock_site_base_url: str) -> None:
    target = ProfileTarget(handle="@nova.wear", platform="instagram", url=f"{mock_site_base_url}/nova.wear")
    connector = SocialProfileConnector(
        "test-run", [target], headless=True, lookback_days=14, human_pause=False
    )

    try:
        accounts = await connector.fetch_accounts()
        posts = await connector.fetch_posts()
    finally:
        await connector.aclose()

    assert accounts == [
        {"handle": "@nova.wear", "display_name": "Nova Wear", "platform": "instagram"}
    ]
    assert len(posts) == 4
    post = next(p for p in posts if p["external_post_id"] == "nova-001")
    assert post["format"] == "meme"
    assert post["theme_tags"] == ["monday-mood", "relatable", "humor"]
    assert post["likes"] == 8420
    assert post["comments"] == 312
    assert post["shares"] == 190


async def test_social_profile_connector_records_video(mock_site_base_url: str) -> None:
    target = ProfileTarget(handle="@nova.wear", platform="instagram", url=f"{mock_site_base_url}/nova.wear")
    connector = SocialProfileConnector(
        "test-run-record", [target], headless=True, record=True, human_pause=False
    )

    try:
        await connector.fetch_accounts()
    finally:
        await connector.aclose()

    video_path = connector.recorded_video_path
    assert video_path is not None
    assert video_path.exists()
    assert video_path.stat().st_size > 0


async def test_social_profile_connector_emits_events(mock_site_base_url: str) -> None:
    from agent_events import AgentEventBus
    from fakeredis.aioredis import FakeRedis

    bus = AgentEventBus(FakeRedis(decode_responses=True))
    target = ProfileTarget(handle="@nova.wear", platform="instagram", url=f"{mock_site_base_url}/nova.wear")
    connector = SocialProfileConnector(
        "test-run-events", [target], headless=True, event_bus=bus, human_pause=False
    )

    try:
        await connector.fetch_accounts()
    finally:
        await connector.aclose()
    await bus.close_run("test-run-events")

    events = [event async for event in bus.subscribe("test-run-events")]
    step_types = [e.step_type for e in events]
    assert "nav" in step_types
    assert "screenshot" in step_types
    assert step_types[-1] == "status"


async def test_social_profile_lookback_filters_old_posts(mock_site_base_url: str) -> None:
    target = ProfileTarget(handle="@nova.wear", platform="instagram", url=f"{mock_site_base_url}/nova.wear")
    connector = SocialProfileConnector(
        "test-lookback", [target], headless=True, lookback_days=1, human_pause=False
    )
    try:
        posts = await connector.fetch_posts()
    finally:
        await connector.aclose()
    assert len(posts) < 4
    assert len(posts) >= 1
