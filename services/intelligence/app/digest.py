from sqlalchemy.ext.asyncio import AsyncSession

from app.clustering import cluster_posts
from app.ingestion_client import IngestedPost
from app.models import Digest


async def generate_digest(
    session: AsyncSession,
    posts: list[IngestedPost],
    *,
    brand_themes: set[str] | None = None,
) -> Digest:
    result = cluster_posts(posts, brand_themes=brand_themes)
    digest = Digest(
        clusters=[c.model_dump() for c in result.clusters],
        trending_themes=result.trending_themes,
        gap_themes=result.gap_themes,
        post_count=len(posts),
    )
    session.add(digest)
    await session.commit()
    await session.refresh(digest)
    return digest
