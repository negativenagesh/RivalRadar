from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_post_columns)


def _ensure_post_columns(sync_conn) -> None:  # noqa: ANN001
    """Add media/metrics columns on existing DBs (create_all does not alter)."""
    from sqlalchemy import text

    statements = [
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS media_urls JSON DEFAULT '[]'",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS media_keys JSON DEFAULT '[]'",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS comment_sample JSON DEFAULT '[]'",
    ]
    for stmt in statements:
        try:
            sync_conn.execute(text(stmt))
        except Exception:
            # SQLite / older Postgres variants — ignore if unsupported
            pass
