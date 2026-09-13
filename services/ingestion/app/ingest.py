from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.connectors.base import Connector, RawAccount, RawPost
from app.models import CompetitorAccount, CompetitorPost, PostFormat
from app.schemas import IngestionRunResult

_KNOWN_PLATFORMS = {
    "instagram",
    "linkedin",
    "x",
    "twitter",
    "youtube",
    "tiktok",
    "threads",
    "mock",
    "web",
}


def _normalize_platform(raw: str | None) -> str:
    p = (raw or "").strip().lower()
    if p == "twitter":
        return "x"
    return p


def platform_from_raw_post(raw: RawPost) -> str | None:
    """Posts store platform in theme_tags, not as a column."""
    for tag in raw.get("theme_tags") or []:
        token = str(tag).split(":", 1)[0].strip().lower()
        if token in _KNOWN_PLATFORMS:
            return _normalize_platform(token)
    return None


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
    existing = await session.scalars(select(CompetitorAccount))
    seen = {(a.handle, _normalize_platform(a.platform)) for a in existing.all()}

    created = 0
    for raw in raw_accounts:
        platform = _normalize_platform(raw["platform"])
        key = (raw["handle"], platform)
        if key in seen:
            continue
        session.add(
            CompetitorAccount(
                handle=raw["handle"],
                display_name=raw["display_name"],
                platform=platform or raw["platform"],
            )
        )
        seen.add(key)
        created += 1
    await session.flush()
    return created


async def _upsert_posts(session: AsyncSession, connector: Connector) -> tuple[int, int]:
    return await _upsert_post_rows(session, await connector.fetch_posts())


def _account_id_for_post(raw: RawPost, accounts: list[CompetitorAccount]) -> str | None:
    handle = raw["account_handle"]
    platform = platform_from_raw_post(raw)
    by_hp = {(a.handle, _normalize_platform(a.platform)): a.id for a in accounts}
    if platform:
        match = by_hp.get((handle, platform))
        if match:
            return match
        for acc in accounts:
            if acc.handle == handle and _normalize_platform(acc.platform) == platform:
                return acc.id
        return None
    same_handle = [a for a in accounts if a.handle == handle]
    if len(same_handle) == 1:
        return same_handle[0].id
    return None


def _clip_image_url(image_url: object) -> str | None:
    if not isinstance(image_url, str) or not image_url:
        return None
    return image_url[:500]


async def _ensure_account_for_post(
    session: AsyncSession,
    raw: RawPost,
    accounts: list[CompetitorAccount],
) -> str | None:
    account_id = _account_id_for_post(raw, accounts)
    if account_id:
        return account_id
    platform = platform_from_raw_post(raw)
    if not platform:
        return None
    handle = raw["account_handle"]
    acc = CompetitorAccount(
        handle=handle,
        display_name=handle,
        platform=platform,
    )
    session.add(acc)
    await session.flush()
    accounts.append(acc)
    return acc.id


async def _upsert_post_rows(session: AsyncSession, raw_posts: list[RawPost]) -> tuple[int, int]:
    accounts = list((await session.scalars(select(CompetitorAccount))).all())
    existing_rows = list((await session.scalars(select(CompetitorPost))).all())
    existing_by_id = {p.external_post_id: p for p in existing_rows}

    created, skipped = 0, 0
    for raw in raw_posts:
        image_url = _clip_image_url(raw.get("image_url"))
        media_keys = list(raw.get("media_keys") or [])
        media_urls = list(raw.get("media_urls") or [])
        existing = existing_by_id.get(raw["external_post_id"])
        if existing is not None:
            if media_keys and not existing.media_keys:
                existing.media_keys = media_keys
                existing.media_urls = media_urls or list(existing.media_urls or [])
                flag_modified(existing, "media_keys")
                flag_modified(existing, "media_urls")
                if image_url:
                    existing.image_url = image_url
            skipped += 1
            continue
        account_id = await _ensure_account_for_post(session, raw, accounts)
        if account_id is None:
            skipped += 1
            continue
        fmt = raw["format"]
        try:
            post_format = PostFormat(fmt)
        except ValueError:
            post_format = PostFormat.FOUNDER_POST
        row = CompetitorPost(
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
            media_urls=media_urls,
            media_keys=media_keys,
            comment_sample=list(raw.get("comment_sample") or []),
            posted_at=datetime.fromisoformat(raw["posted_at"].replace("Z", "+00:00")),
        )
        session.add(row)
        existing_by_id[raw["external_post_id"]] = row
        created += 1
    await session.flush()
    return created, skipped
