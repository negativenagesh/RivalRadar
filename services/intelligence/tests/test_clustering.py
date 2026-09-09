from app.clustering import cluster_posts

from tests.fixtures import make_post


def test_posts_group_by_format_and_dominant_theme() -> None:
    posts = [
        make_post("p1", format="meme", themes=["monday-mood", "humor"]),
        make_post("p2", format="meme", themes=["monday-mood", "relatable"]),
        make_post("p3", format="founder_post", themes=["behind-the-scenes"]),
    ]

    result = cluster_posts(posts)

    assert len(result.clusters) == 2
    meme_cluster = next(c for c in result.clusters if c.format == "meme")
    assert meme_cluster.post_count == 2
    assert meme_cluster.dominant_theme == "monday-mood"


def test_clusters_sorted_by_total_engagement_descending() -> None:
    posts = [
        make_post("low", format="meme", likes=10, comments=1, shares=0),
        make_post("high", format="founder_post", themes=["founder"], likes=5000, comments=200, shares=100),
    ]

    result = cluster_posts(posts)

    assert result.clusters[0].format == "founder_post"
    assert result.clusters[0].total_engagement > result.clusters[1].total_engagement


def test_top_post_in_cluster_is_highest_engagement() -> None:
    posts = [
        make_post("weak", themes=["x"], likes=10, comments=0, shares=0, caption="weak post"),
        make_post("strong", themes=["x"], likes=9000, comments=500, shares=300, caption="strong post"),
    ]

    result = cluster_posts(posts)

    assert result.clusters[0].top_post_id == "strong"
    assert result.clusters[0].top_post_caption == "strong post"


def test_trending_themes_ranked_by_frequency() -> None:
    posts = [
        make_post("p1", themes=["sustainability"]),
        make_post("p2", themes=["sustainability"]),
        make_post("p3", themes=["sustainability"]),
        make_post("p4", themes=["humor"]),
    ]

    result = cluster_posts(posts)

    assert result.trending_themes[0] == "sustainability"


def test_gap_themes_exclude_brand_themes_and_single_account_themes() -> None:
    posts = [
        make_post("p1", account_id="acc-1", themes=["sustainability"]),
        make_post("p2", account_id="acc-2", themes=["sustainability"]),
        make_post("p3", account_id="acc-1", themes=["niche-only-one-account"]),
        make_post("p4", account_id="acc-1", themes=["already-our-thing"]),
        make_post("p5", account_id="acc-2", themes=["already-our-thing"]),
    ]

    result = cluster_posts(posts, brand_themes={"already-our-thing"})

    assert "sustainability" in result.gap_themes
    assert "niche-only-one-account" not in result.gap_themes
    assert "already-our-thing" not in result.gap_themes


def test_untagged_posts_get_their_own_bucket() -> None:
    posts = [make_post("p1", themes=[])]

    result = cluster_posts(posts)

    assert result.clusters[0].dominant_theme == "untagged"


def test_empty_post_list_returns_empty_digest() -> None:
    result = cluster_posts([])

    assert result.clusters == []
    assert result.trending_themes == []
    assert result.gap_themes == []
