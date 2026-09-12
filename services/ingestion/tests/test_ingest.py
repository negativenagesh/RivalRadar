from app.connectors.base import RawAccount, RawPost
from app.connectors.fixture import FixtureConnector
from app.ingest import persist_raw_buffers, run_ingestion
from app.models import CompetitorAccount, CompetitorPost, PostFormat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def test_run_ingestion_creates_accounts_and_posts(session: AsyncSession) -> None:
    result = await run_ingestion(session, FixtureConnector())

    assert result.accounts_ingested == 3
    assert result.posts_ingested == 10
    assert result.posts_skipped_duplicate == 0

    accounts = (await session.scalars(select(CompetitorAccount))).all()
    posts = (await session.scalars(select(CompetitorPost))).all()
    assert len(accounts) == 3
    assert len(posts) == 10


async def test_run_ingestion_is_idempotent(session: AsyncSession) -> None:
    connector = FixtureConnector()
    await run_ingestion(session, connector)
    second_result = await run_ingestion(session, connector)

    assert second_result.accounts_ingested == 0
    assert second_result.posts_ingested == 0
    assert second_result.posts_skipped_duplicate == 10


async def test_post_engagement_score_weights_shares_and_comments(session: AsyncSession) -> None:
    await run_ingestion(session, FixtureConnector())
    post = (
        await session.scalars(
            select(CompetitorPost).where(CompetitorPost.external_post_id == "nova-001")
        )
    ).one()

    assert post.engagement_score == 8420 + 312 * 3 + 190 * 5
    assert post.themes == ["monday-mood", "relatable", "humor"]


class _BufferConnector:
    def __init__(self) -> None:
        self._accounts = [
            RawAccount(handle="@pixisai", display_name="Pixis", platform="linkedin"),
        ]
        self._posts = [
            RawPost(
                account_handle="@pixisai",
                external_post_id="linkedin:urn-li-activity-1",
                format="reel",
                theme_tags=["linkedin", "source:oss"],
                caption="A post",
                image_url="https://example.com/" + ("x" * 600),
                likes=1,
                comments=0,
                shares=0,
                posted_at="2026-09-12T12:00:00Z",
                views=10,
                media_urls=[],
                media_keys=["media/run/post.jpg"],
            )
        ]


async def test_persist_raw_buffers_without_fetch(session: AsyncSession) -> None:
    created = await persist_raw_buffers(session, _BufferConnector())
    assert created == 1
    post = (
        await session.scalars(
            select(CompetitorPost).where(CompetitorPost.external_post_id == "linkedin:urn-li-activity-1")
        )
    ).one()
    assert post.format == PostFormat.FOUNDER_POST
    assert post.image_url is not None and len(post.image_url) <= 500
    assert post.media_keys == ["media/run/post.jpg"]

