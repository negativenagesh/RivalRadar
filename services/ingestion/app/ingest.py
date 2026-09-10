from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import Connector
from app.models import CompetitorAccount, CompetitorPost, PostFormat
from app.schemas import IngestionRunResult


async def run_ingestion(session: AsyncSession, connector: Connector) -> IngestionRunResult:
    try:
        accounts_ingested = await _upsert_accounts(session, connector)
        posts_ingested, posts_skipped = await _upsert_posts(session, connector)
        await session.commit()
    finally:
        aclose = getattr(connector, "aclose", None)
        if aclose is not None:
            await aclose()
    return IngestionRunResult(
        accounts_ingested=accounts_ingested,
        posts_ingested=posts_ingested,
        posts_skipped_duplicate=posts_skipped,
    )


async def _upsert_accounts(session: AsyncSession, connector: Connector) -> int:
    raw_accounts = await connector.fetch_accounts()
    existing = await session.scalars(select(CompetitorAccount.handle))
    existing_handles = set(existing.all())

    created = 0
    for raw in raw_accounts:
        if raw["handle"] in existing_handles:
            continue
        session.add(
            CompetitorAccount(
                handle=raw["handle"],
                display_name=raw["display_name"],
                platform=raw["platform"],
            )
        )
        created += 1
    await session.flush()
    return created


async def _upsert_posts(session: AsyncSession, connector: Connector) -> tuple[int, int]:
    raw_posts = await connector.fetch_posts()

    accounts = await session.scalars(select(CompetitorAccount))
    handle_to_id = {a.handle: a.id for a in accounts}

    existing = await session.scalars(select(CompetitorPost.external_post_id))
    existing_ids = set(existing.all())

    created, skipped = 0, 0
    for raw in raw_posts:
        if raw["external_post_id"] in existing_ids:
            skipped += 1
            continue
        account_id = handle_to_id.get(raw["account_handle"])
        if account_id is None:
            skipped += 1
            continue
        session.add(
            CompetitorPost(
                account_id=account_id,
                external_post_id=raw["external_post_id"],
                format=PostFormat(raw["format"]),
                theme_tags=",".join(raw["theme_tags"]),
                caption=raw["caption"],
                image_url=raw["image_url"],
                likes=raw["likes"],
                comments=raw["comments"],
                shares=raw["shares"],
                posted_at=datetime.fromisoformat(raw["posted_at"].replace("Z", "+00:00")),
            )
        )
        created += 1
    await session.flush()
    return created, skipped
