import pytest
from app.comment_drop import PAUSE_MAX_S, PAUSE_MIN_S, CommentDropError, drop_comment, validate_drop


def test_comment_drop_requires_human_approval() -> None:
    with pytest.raises(CommentDropError, match="approval"):
        validate_drop(
            platform="linkedin",
            url="https://www.linkedin.com/feed/update/urn:li:activity:1",
            text="sharp take",
            approved=False,
        )


def test_comment_drop_rejects_youtube_and_empty() -> None:
    with pytest.raises(CommentDropError, match="not supported"):
        validate_drop(
            platform="youtube",
            url="https://www.youtube.com/watch?v=abc",
            text="hi",
            approved=True,
        )
    with pytest.raises(CommentDropError, match="empty"):
        validate_drop(
            platform="x",
            url="https://x.com/a/status/1",
            text="  ",
            approved=True,
        )


def test_human_delays_are_ten_to_fifteen_seconds() -> None:
    assert PAUSE_MIN_S == 10.0
    assert PAUSE_MAX_S == 15.0


async def test_drop_comment_refuses_without_connection() -> None:
    with pytest.raises(CommentDropError, match="not connected"):
        await drop_comment(
            platform="linkedin",
            url="https://www.linkedin.com/feed/update/urn:li:activity:1",
            text="nice receipts",
            approved=True,
            platform_sessions={},
        )
