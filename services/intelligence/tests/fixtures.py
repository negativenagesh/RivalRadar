from app.ingestion_client import IngestedPost


def make_post(
    id: str,
    *,
    account_id: str = "acc-1",
    format: str = "meme",
    themes: list[str] | None = None,
    likes: int = 100,
    comments: int = 10,
    shares: int = 5,
    caption: str = "a post",
) -> IngestedPost:
    themes = themes if themes is not None else ["monday-mood"]
    return IngestedPost(
        id=id,
        account_id=account_id,
        external_post_id=id,
        format=format,
        theme_tags=",".join(themes),
        caption=caption,
        image_url=None,
        likes=likes,
        comments=comments,
        shares=shares,
        posted_at="2026-08-25T14:00:00Z",
        engagement_score=likes + comments * 3 + shares * 5,
        themes=themes,
    )
