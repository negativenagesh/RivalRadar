from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import Connector, RawAccount, RawPost
from app.models import CompetitorAccount, CompetitorPost, PostFormat
from app.schemas import IngestionRunResult


def _iter_connectors(connector: object) -> list[object]:
    inner = getattr(connector, "_connectors", None)
    if inner:
        return list(inner)
    return [connector]


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


async def persist_raw_buffers(session: AsyncSession, connector: object) -> int:
    """Flush whatever the connector has collected so far (Stop Scout / checkpoints)."""
    created = 0
    for child in _iter_connectors(connector):
        accounts = list(getattr(child, "_accounts", []) or [])
        posts = list(getattr(child, "_posts", []) or [])
        if accounts:
            await _upsert_account_rows(session, accounts)
        if posts:
            n, _ = await _upsert_post_rows(session, posts)
            created += n
    await session.commit()
    return created


def buffer_counts(connector: object) -> tuple[int, int]:
    accounts = 0
    posts = 0
    found = False
    for child in _iter_connectors(connector):
        if hasattr(child, "_accounts") or hasattr(child, "_posts"):
            found = True
        accounts += len(list(getattr(child, "_accounts", []) or []))
        posts += len(list(getattr(child, "_posts", []) or []))
    if not found:
        return 0, 0
    return accounts, posts


async def _upsert_accounts(session: AsyncSession, connector: Connector) -> int:
    return await _upsert_account_rows(session, await connector.fetch_accounts())


async def _upsert_account_rows(session: AsyncSession, raw_accounts: list[RawAccount]) -> int:
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
        existing_handles.add(raw["handle"])
        created += 1
    await session.flush()
    return created


async def _upsert_posts(session: AsyncSession, connector: Connector) -> tuple[int, int]:
    return await _upsert_post_rows(session, await connector.fetch_posts())


async def _upsert_post_rows(session: AsyncSession, raw_posts: list[RawPost]) -> tuple[int, int]:
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
        fmt = raw["format"]
        try:
            post_format = PostFormat(fmt)
        except ValueError:
            post_format = PostFormat.FOUNDER_POST
        image_url = raw.get("image_url")
        if isinstance(image_url, str) and len(image_url) > 500:
            image_url = image_url[:500]
        session.add(
            CompetitorPost(
                account_id=account_id,
                external_post_id=raw["external_post_id"],
                format=post_format,
                theme_tags=",".join(raw["theme_tags"]),
                caption=raw["caption"],
                image_url=image_url,
                likes=raw["likes"],
                comments=raw["comments"],
                shares=raw["shares"],
                views=int(raw.get("views") or 0),
                media_urls=list(raw.get("media_urls") or []),
                media_keys=list(raw.get("media_keys") or []),
                comment_sample=list(raw.get("comment_sample") or []),
                posted_at=datetime.fromisoformat(raw["posted_at"].replace("Z", "+00:00")),
            )
        )
        existing_ids.add(raw["external_post_id"])
        created += 1
    await session.flush()
    return created, skipped
