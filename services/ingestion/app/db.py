from collections.abc import AsyncGenerator
from contextlib import suppress

from sqlalchemy import Connection, text
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
        await conn.run_sync(_ensure_account_handle_platform)
    await _ensure_run_status_cancelled()


def _ensure_post_columns(sync_conn: Connection) -> None:
    """Add media/metrics columns on existing DBs (create_all does not alter)."""
    statements = [
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS media_urls JSON DEFAULT '[]'",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS media_keys JSON DEFAULT '[]'",
        "ALTER TABLE competitor_posts ADD COLUMN IF NOT EXISTS comment_sample JSON DEFAULT '[]'",
    ]
    for stmt in statements:
        with suppress(Exception):
            sync_conn.execute(text(stmt))


def _ensure_account_handle_platform(sync_conn: Connection) -> None:
    """Allow @pixisai on YouTube and LinkedIn at once. create_all does not drop uniques."""
    for stmt in (
        "ALTER TABLE competitor_accounts DROP CONSTRAINT IF EXISTS competitor_accounts_handle_key",
        "DROP INDEX IF EXISTS competitor_accounts_handle_key",
        # SQLAlchemy unique=True previously created this unique index.
        "DROP INDEX IF EXISTS ix_competitor_accounts_handle",
        "CREATE INDEX IF NOT EXISTS ix_competitor_accounts_handle ON competitor_accounts (handle)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_account_handle_platform ON competitor_accounts (handle, platform)",
    ):
        with suppress(Exception):
            sync_conn.execute(text(stmt))


async def _ensure_run_status_cancelled() -> None:
    """Postgres native enums are not altered by create_all; ADD VALUE needs autocommit."""
    async with engine.connect() as conn:
        auto = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for label in ("CANCELLED", "cancelled"):
            with suppress(Exception):
                await auto.execute(
                    text(f"ALTER TYPE runstatus ADD VALUE IF NOT EXISTS '{label}'")
                )