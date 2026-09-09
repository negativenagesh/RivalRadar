from collections.abc import AsyncGenerator

import pytest_asyncio
from app.main import app
from httpx import ASGITransport, AsyncClient

from llm_provider import get_llm_provider
from tests.fakes import FakeLLMProvider


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_llm_provider] = lambda: FakeLLMProvider(
        completion='{"safe": true, "reason": ""}'
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
