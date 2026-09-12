from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.connectors.youtube.api import YouTubeDataClient, channel_to_raw_account, video_to_raw_post
from app.date_window import DateWindow
from app.connectors.youtube.parse import parse_youtube_ref


def test_parse_youtube_at_handle() -> None:
    ref = parse_youtube_ref("https://www.youtube.com/@PixisAI")
    assert ref is not None
    assert ref.handle == "PixisAI"
    assert ref.channel_id is None


def test_parse_youtube_channel_id() -> None:
    ref = parse_youtube_ref("https://youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw")
    assert ref is not None
    assert ref.channel_id == "UC_x5XG1OV2P6uZZ5FSM9Ttw"


def test_parse_bare_handle() -> None:
    ref = parse_youtube_ref("@acme")
    assert ref is not None
    assert ref.handle == "acme"


@pytest.mark.asyncio
async def test_youtube_client_resolves_and_filters_lookback() -> None:
    # Implemented with respx-free manual mock via ASGI-less httpx MockTransport
    cutoff_keep = (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff_drop = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "/channels" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "UCtest",
                            "snippet": {
                                "title": "Acme",
                                "customUrl": "@acme",
                                "description": "demo",
                            },
                            "statistics": {"subscriberCount": "10", "videoCount": "2"},
                            "contentDetails": {
                                "relatedPlaylists": {"uploads": "UUtest"}
                            },
                        }
                    ]
                },
            )
        if "/playlistItems" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "vid_new"}},
                        {"contentDetails": {"videoId": "vid_old"}},
                    ]
                },
            )
        if "/videos" in url:
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": "vid_new",
                            "snippet": {
                                "title": "Fresh drop",
                                "description": "new",
                                "publishedAt": cutoff_keep,
                                "thumbnails": {"high": {"url": "https://img/new.jpg"}},
                            },
                            "statistics": {
                                "viewCount": "1000",
                                "likeCount": "50",
                                "commentCount": "5",
                            },
                        },
                        {
                            "id": "vid_old",
                            "snippet": {
                                "title": "Old drop",
                                "description": "old",
                                "publishedAt": cutoff_drop,
                                "thumbnails": {"high": {"url": "https://img/old.jpg"}},
                            },
                            "statistics": {
                                "viewCount": "9",
                                "likeCount": "1",
                                "commentCount": "0",
                            },
                        },
                    ]
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = YouTubeDataClient("fake-key", client=http)
        channel = await client.resolve_channel(handle="acme", channel_id=None)
        videos = await client.fetch_recent_videos(channel, window=DateWindow.from_lookback(3))

    assert channel["id"] == "UCtest"
    assert len(videos) == 1
    assert videos[0]["id"] == "vid_new"

    account = channel_to_raw_account(channel, "youtube_api")
    post = video_to_raw_post(videos[0], account_handle=account["handle"], source="youtube_api")
    assert account["platform"] == "youtube"
    assert "source:youtube_api" in post["theme_tags"]
    assert post["views"] == 1000
    assert post["shares"] == 0
