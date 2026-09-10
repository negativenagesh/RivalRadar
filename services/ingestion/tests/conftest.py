from collections.abc import AsyncGenerator

import pytest_asyncio
from agent_events import AgentEventBus
from app.agent_events_bus import get_event_bus
from app.db import Base, get_session
from app.main import app
from fakeredis.aioredis import FakeRedis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A factory that always hands back the same test session, so the
    background ingestion task and the test's own assertions share state."""

    class _SingleSessionFactory:
        def __call__(self) -> AsyncSession:
            return session

    return _SingleSessionFactory()  # type: ignore[return-value]


@pytest_asyncio.fixture
async def event_bus() -> AgentEventBus:
    return AgentEventBus(FakeRedis(decode_responses=True))


@pytest_asyncio.fixture
async def client(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: AgentEventBus,
) -> AsyncGenerator[AsyncClient]:
    async def override_get_session() -> AsyncGenerator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_event_bus] = lambda: event_bus
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
    del app.state.session_factory
