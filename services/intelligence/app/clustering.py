from collections import Counter, defaultdict

from pydantic import BaseModel

from app.ingestion_client import IngestedPost


class Cluster(BaseModel):
    format: str
    dominant_theme: str
    post_count: int
    total_engagement: int
    avg_engagement: float
    top_post_id: str
    top_post_caption: str
    account_ids: list[str]


class DigestResult(BaseModel):
    clusters: list[Cluster]
    trending_themes: list[str]
    gap_themes: list[str]


def cluster_posts(posts: list[IngestedPost], *, brand_themes: set[str] | None = None) -> DigestResult:
    """Group posts by format + dominant theme tag, score by engagement.

    Deliberately rule/tag-based rather than embeddings-based for v1: posts
    already carry structured `format` and `theme_tags` from ingestion, so
    grouping on those fields is exact, fully explainable (no similarity
    threshold to tune), and needs no vector index. See
    services/intelligence/README.md for the full trade-off discussion.
    """
    brand_themes = brand_themes or set()

    groups: dict[tuple[str, str], list[IngestedPost]] = defaultdict(list)
    for post in posts:
        dominant_theme = _dominant_theme(post["themes"])
        groups[(post["format"], dominant_theme)].append(post)

    clusters = [
        _build_cluster(fmt, theme, group_posts) for (fmt, theme), group_posts in groups.items()
    ]
    clusters.sort(key=lambda c: c.total_engagement, reverse=True)

    theme_counts = Counter(theme for post in posts for theme in post["themes"])
    trending_themes = [theme for theme, _count in theme_counts.most_common(5)]

    accounts_per_theme: dict[str, set[str]] = defaultdict(set)
    for post in posts:
        for theme in post["themes"]:
            accounts_per_theme[theme].add(post["account_id"])

    gap_themes = sorted(
        (
            theme
            for theme, accounts in accounts_per_theme.items()
            if len(accounts) >= 2 and theme not in brand_themes
        ),
        key=lambda t: theme_counts[t],
        reverse=True,
    )

    return DigestResult(clusters=clusters, trending_themes=trending_themes, gap_themes=gap_themes)


def _dominant_theme(themes: list[str]) -> str:
    return themes[0] if themes else "untagged"


def _build_cluster(fmt: str, theme: str, posts: list[IngestedPost]) -> Cluster:
    total_engagement = sum(p["engagement_score"] for p in posts)
    top_post = max(posts, key=lambda p: p["engagement_score"])
    return Cluster(
        format=fmt,
        dominant_theme=theme,
        post_count=len(posts),
        total_engagement=total_engagement,
        avg_engagement=total_engagement / len(posts),
        top_post_id=top_post["id"],
        top_post_caption=top_post["caption"],
        account_ids=sorted({p["account_id"] for p in posts}),
    )
