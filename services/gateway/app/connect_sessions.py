"""In-memory Connect session registry (gateway side)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

PLATFORM_LOGIN_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/login",
    "x": "https://x.com/i/flow/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "tiktok": "https://www.tiktok.com/login",
    "threads": "https://www.threads.net/login",
    "facebook": "https://www.facebook.com/login",
    "meta": "https://www.instagram.com/accounts/login/",
}


@dataclass
class ConnectSession:
    session_id: str
    workspace_id: str
    platform: str
    login_url: str
    status: str = "awaiting_login"
    detail: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def expired(self) -> bool:
        return datetime.now(UTC) > self.created_at + timedelta(minutes=15)


_SESSIONS: dict[str, ConnectSession] = {}


def put_session(session: ConnectSession) -> None:
    _SESSIONS[session.session_id] = session


def get_session(session_id: str) -> ConnectSession | None:
    session = _SESSIONS.get(session_id)
    if session is None:
        return None
    if session.expired and session.status == "awaiting_login":
        session.status = "expired"
        session.detail = "Connect session timed out"
    return session


def pop_session(session_id: str) -> ConnectSession | None:
    return _SESSIONS.pop(session_id, None)


def login_url_for(platform: str) -> str:
    return PLATFORM_LOGIN_URLS.get(platform.lower(), f"https://www.{platform}.com/login")
