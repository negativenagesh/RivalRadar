"""YouTube connector: Data API v3 primary, yt-dlp fallback, Playwright operator frames."""

from __future__ import annotations

import asyncio
import html
import random
import tempfile
from pathlib import Path

from agent_events import AgentEvent, AgentEventBus
from agent_events.schema import StepType

from app.connectors.base import RawAccount, RawPost
from app.connectors.social_profile.browser import BrowserSession
from app.connectors.social_profile.targets import ProfileTarget
from app.connectors.youtube.api import (
    YouTubeApiError,
    YouTubeDataClient,
    channel_to_raw_account,
    video_to_raw_post,
)
from app.connectors.youtube.media import enrich_posts_media
from app.connectors.youtube.parse import parse_youtube_ref
from app.connectors.youtube.ytdlp_fallback import YtDlpError, fetch_channel_via_ytdlp
from app.date_window import DateWindow
from app.objectstore import ObjectStore

_AGENT_ID = "ingestion.youtube"
_SERVICE = "ingestion"


class YouTubeConnector:
    """Fetches channel + recent uploads within a date window.

    Structured data: YouTube Data API v3, else yt-dlp.
    Operator theater: Playwright screenshots only for API-backed digests.
    yt-dlp path emits text intel artifacts (no screenshots).
    """

    def __init__(
        self,
        run_id: str,
        targets: list[ProfileTarget],
        *,
        lookback_days: int = 3,
        date_from=None,
        date_to=None,
        window: DateWindow | None = None,
        api_key: str | None = None,
        headless: bool = True,
        record: bool = False,
        event_bus: AgentEventBus | None = None,
        human_pause: bool = True,
        object_store: ObjectStore | None = None,
    ) -> None:
        self._run_id = run_id
        self._targets = targets
        self._window = window or DateWindow.resolve(
            lookback_days=lookback_days, date_from=date_from, date_to=date_to
        )
        self._lookback_days = self._window.span_days
        self._api_key = api_key
        self._headless = headless
        self._record = record
        self._event_bus = event_bus
        self._human_pause = human_pause
        self._object_store = object_store
        self._session: BrowserSession | None = None
        self._sequence = 0
        self._accounts: list[RawAccount] = []
        self._posts: list[RawPost] = []
        self._sources_used: list[str] = []
        self._loaded = False

    @property
    def recorded_video_path(self) -> Path | None:
        return self._session.recorded_video_path if self._session else None

    @property
    def sources_used(self) -> list[str]:
        return list(self._sources_used)

    @property
    def screenshot_keys(self) -> list[str]:
        return []

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

    async def fetch_accounts(self) -> list[RawAccount]:
        await self._ensure_loaded()
        return list(self._accounts)

    async def fetch_posts(self) -> list[RawPost]:
        await self._ensure_loaded()
        return list(self._posts)

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        for target in self._targets:
            await self._ingest_target(target)

        used_api = "youtube_api" in self._sources_used
        used_ytdlp = "yt_dlp" in self._sources_used
        if used_ytdlp:
            await self._emit_ytdlp_intel()
        if used_api and not used_ytdlp:
            await self._operator_frames()
        elif used_api and used_ytdlp:
            # Mixed: still show theater for API portion only
            await self._operator_frames()

        if self._posts:
            self._posts = await enrich_posts_media(
                self._posts,
                run_id=self._run_id,
                store=self._object_store,
                api_key=self._api_key if used_api else None,
            )
        self._loaded = True

    async def _ingest_target(self, target: ProfileTarget) -> None:
        ref = parse_youtube_ref(target.url or target.handle)
        if ref is None:
            await self._emit("error", {"detail": f"Invalid YouTube target: {target.handle}"})
            return

        await self._emit("action", {"detail": "resolve_channel", "handle": ref.handle})
        account: RawAccount | None = None
        posts: list[RawPost] = []
        source = "youtube_api"

        if self._api_key:
            try:
                async with YouTubeDataClient(self._api_key) as client:
                    channel = await client.resolve_channel(
                        handle=ref.handle, channel_id=ref.channel_id
                    )
                    await self._emit("action", {"detail": "list_uploads", "channel_id": channel["id"]})
                    videos = await client.fetch_recent_videos(channel, window=self._window)
                    account = channel_to_raw_account(channel, source)
                    posts = [
                        video_to_raw_post(v, account_handle=account["handle"], source=source)
                        for v in videos
                    ]
                    self._sources_used.append("youtube_api")
            except YouTubeApiError as exc:
                await self._emit("log", {"message": f"YouTube API failed; trying yt-dlp — {exc}"})
                account = None

        if account is None:
            source = "yt_dlp"
            try:
                url = ref.url or f"https://www.youtube.com/@{ref.handle}"
                await self._emit("action", {"detail": "yt_dlp_fallback", "url": url})
                account, posts = await fetch_channel_via_ytdlp(url, window=self._window)
                self._sources_used.append("yt_dlp")
            except YtDlpError as exc:
                await self._emit("error", {"detail": f"yt-dlp failed: {exc}"})
                return

        self._accounts.append(account)
        self._posts.extend(posts)
        await self._emit(
            "action",
            {
                "detail": "ingest_video",
                "handle": account["handle"],
                "count": len(posts),
                "source": source,
                "lookback_days": self._lookback_days,
                "date_from": self._window.date_from.isoformat(),
                "date_to": self._window.date_to.isoformat(),
            },
        )

    async def _emit_ytdlp_intel(self) -> None:
        """Text intel panel payload — no screenshots for yt-dlp hops."""
        videos = []
        for p in self._posts:
            if "source:yt_dlp" not in p.get("theme_tags", []):
                continue
            title = (p["caption"] or "").split("\n", 1)[0][:160]
            videos.append(
                {
                    "title": title,
                    "views": int(p.get("views") or 0),
                    "likes": p["likes"],
                    "comments": p["comments"],
                    "posted_at": p["posted_at"],
                    "url": next(
                        (t[5:] for t in p.get("theme_tags", []) if t.startswith("link:")),
                        f"https://www.youtube.com/watch?v={p['external_post_id']}",
                    ),
                    "external_post_id": p["external_post_id"],
                }
            )
        channel_title = self._accounts[0]["display_name"] if self._accounts else "YouTube"
        await self._emit(
            "artifact",
            {
                "kind": "ytdlp_intel",
                "channel_title": channel_title,
                "accounts": [
                    {"handle": a["handle"], "display_name": a["display_name"]} for a in self._accounts
                ],
                "videos": videos,
                "date_from": self._window.date_from.isoformat(),
                "date_to": self._window.date_to.isoformat(),
            },
        )
        await self._emit(
            "log",
            {
                "message": (
                    f"yt-dlp intel: {len(videos)} videos · "
                    f"{self._window.date_from} → {self._window.date_to} (no screenshots)"
                )
            },
        )

    async def _operator_frames(self) -> None:
        """Render an offline HTML digest and screenshot it for the Operator console."""
        if not self._accounts and not self._posts:
            return
        html_doc = _render_operator_html(self._accounts, self._posts, self._window)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "youtube-operator.html"
            path.write_text(html_doc, encoding="utf-8")
            self._session = await BrowserSession(
                headless=self._headless, record=self._record
            ).__aenter__()
            assert self._session.page is not None
            await self._emit("nav", {"url": path.as_uri()})
            await self._session.page.goto(path.as_uri(), wait_until="domcontentloaded")
            if self._human_pause:
                pause = random.uniform(2.0, 4.0)
                await self._emit("action", {"detail": f"human_pause {pause:.1f}s"})
                await asyncio.sleep(pause)
            await self._session.page.mouse.wheel(0, 500)
            if self._human_pause:
                pause = random.uniform(2.0, 4.0)
                await self._emit("action", {"detail": f"human_pause {pause:.1f}s"})
                await asyncio.sleep(pause)
            await self._emit_screenshot()

    async def _emit(self, step_type: StepType, payload: dict[str, object]) -> None:
        if self._event_bus is None:
            return
        self._sequence += 1
        await self._event_bus.publish(
            AgentEvent(
                run_id=self._run_id,
                agent_id=_AGENT_ID,
                service=_SERVICE,
                step_type=step_type,
                payload=payload,
                sequence=self._sequence,
            )
        )

    async def _emit_screenshot(self) -> None:
        if self._event_bus is None or self._session is None:
            return
        frame = await self._session.screenshot_jpeg_b64()
        await self._emit("screenshot", {"jpeg_b64": frame})


def _render_operator_html(
    accounts: list[RawAccount], posts: list[RawPost], window: DateWindow
) -> str:
    cards = []
    for p in posts:
        views = int(p.get("views") or 0)
        cards.append(
            "<article class='post-card'>"
            f"<h3>{html.escape(p['caption'][:120])}</h3>"
            f"<p>{p['likes']} likes · {p['comments']} comments · {views} views</p>"
            f"<time>{html.escape(p['posted_at'])}</time>"
            "</article>"
        )
    headers = "".join(
        f"<li>{html.escape(a['display_name'])} ({html.escape(a['handle'])})</li>"
        for a in accounts
    )
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>YouTube scout digest</title>
<style>
body{{font-family:system-ui;background:#0b0b0b;color:#eee;padding:24px}}
h1{{color:#9fef00}} .post-card{{border:1px solid #333;margin:12px 0;padding:12px;border-radius:12px}}
</style></head><body>
<h1>YouTube operator digest</h1>
<p>Window {window.date_from.isoformat()} → {window.date_to.isoformat()} ({window.span_days}d)</p>
<ul>{headers}</ul>
{"".join(cards) or "<p>No uploads in window</p>"}
</body></html>"""
