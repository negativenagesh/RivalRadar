from collections.abc import AsyncGenerator

import pytest_asyncio
from app.main import app
from app.routes import operator_provider
from httpx import ASGITransport, AsyncClient

from llm_provider import get_llm_provider
from tests.fakes import FakeLLMProvider


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    fake = FakeLLMProvider(
        completion="a generated caption", image_concept="a generated image concept"
    )
    app.dependency_overrides[get_llm_provider] = lambda: fake
    app.dependency_overrides[operator_provider] = lambda: fake
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
