"""In-memory Connect session registry (gateway side)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

PLATFORM_LOGIN_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/login",
    "x": "https://x.com/i/flow/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "tiktok": "https://www.tiktok.com/login",
    "threads": "https://www.threads.net/login",
    "facebook": "https://www.facebook.com/login",
    "meta": "https://www.instagram.com/accounts/login/",
}

# Prefer home/feed when reseeding a saved session so platforms skip login UI.
PLATFORM_HOME_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/feed/",
    "x": "https://x.com/home",
    "instagram": "https://www.instagram.com/",
    "tiktok": "https://www.tiktok.com/foryou",
    "threads": "https://www.threads.net/",
    "facebook": "https://www.facebook.com/",
    "meta": "https://www.instagram.com/",
}

_AUTH_COOKIE_NAMES = {
    "li_at",
    "sessionid",
    "auth_token",
    "ct0",
    "sid",
    "sessionid_ss",
    "tt_chain_token",
    "sid_tt",
    "csrftoken",
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
        return datetime.now(UTC) > self.created_at + timedelta(minutes=30)


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


def home_url_for(platform: str) -> str:
    key = platform.lower()
    return PLATFORM_HOME_URLS.get(key, login_url_for(key))


def connect_open_url(platform: str, *, has_saved_session: bool) -> str:
    """Open home when we already have vaulted cookies so soft-reconnect works."""
    if has_saved_session:
        return home_url_for(platform)
    return login_url_for(platform)


def expires_at_from_cookies(cookies: list[dict[str, Any]]) -> datetime | None:
    """Pick a vault expiry from auth cookies; default 14 days if none have expires."""
    now = datetime.now(UTC)
    candidates: list[datetime] = []
    for cookie in cookies:
        name = str(cookie.get("name") or "").lower()
        expires = cookie.get("expires")
        if not isinstance(expires, (int, float)) or expires <= 0:
            continue
        if name not in _AUTH_COOKIE_NAMES and not name.startswith("session"):
            continue
        try:
            candidates.append(datetime.fromtimestamp(float(expires), UTC))
        except (OverflowError, OSError, ValueError):
            continue
    if not candidates:
        return now + timedelta(days=14)
    earliest = min(candidates)
    # Soft floor: at least 1 day so we do not immediately flip needs_reconnect
    floor = now + timedelta(days=1)
    ceiling = now + timedelta(days=30)
    if earliest < floor:
        return floor
    if earliest > ceiling:
        return ceiling
    return earliest
