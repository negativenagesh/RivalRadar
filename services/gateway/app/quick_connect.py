"""Quick Connect — one-time pairing codes + cookie vault without noVNC."""

from __future__ import annotations

import logging
import secrets
import string
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_TTL = timedelta(minutes=5)
_CODE_LEN = 6

# Domains + required auth cookie names for extension capture.
PLATFORM_COOKIE_SPEC: dict[str, dict[str, Any]] = {
    "linkedin": {
        "domains": [".linkedin.com", "www.linkedin.com"],
        "required": ["li_at"],
        "optional": ["JSESSIONID", "li_a"],
        "default_domain": ".linkedin.com",
    },
    "x": {
        "domains": [".x.com", ".twitter.com", "x.com", "twitter.com"],
        "required": ["auth_token"],
        "optional": ["ct0"],
        "default_domain": ".x.com",
    },
    "instagram": {
        "domains": [".instagram.com", "www.instagram.com"],
        "required": ["sessionid"],
        "optional": ["csrftoken", "ds_user_id"],
        "default_domain": ".instagram.com",
    },
    "tiktok": {
        "domains": [".tiktok.com", "www.tiktok.com"],
        "required": ["sessionid"],
        "optional": ["tt_chain_token", "sid_tt", "sid_guard"],
        "default_domain": ".tiktok.com",
    },
    "threads": {
        "domains": [".threads.net", "www.threads.net"],
        "required": ["sessionid"],
        "optional": ["csrftoken"],
        "default_domain": ".threads.net",
    },
}


@dataclass
class PairingCode:
    code: str
    workspace_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    consumed: bool = False

    @property
    def expired(self) -> bool:
        return datetime.now(UTC) > self.created_at + _CODE_TTL


_PAIRINGS: dict[str, PairingCode] = {}
_LOCK = threading.Lock()


def issue_pairing_code(workspace_id: str = "default") -> tuple[str, int]:
    """Return (code, expires_in_seconds)."""
    with _LOCK:
        _purge_locked()
        for _ in range(20):
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))
            if code not in _PAIRINGS:
                _PAIRINGS[code] = PairingCode(code=code, workspace_id=workspace_id or "default")
                return code, int(_CODE_TTL.total_seconds())
    raise RuntimeError("Could not allocate pairing code")


def consume_pairing_code(code: str, workspace_id: str = "default") -> bool:
    """Validate and consume a one-time pairing code. Returns True if accepted."""
    key = (code or "").strip().upper()
    if not key:
        return False
    with _LOCK:
        _purge_locked()
        entry = _PAIRINGS.get(key)
        if entry is None or entry.consumed or entry.expired:
            return False
        if entry.workspace_id != (workspace_id or "default"):
            return False
        entry.consumed = True
        return True


def _purge_locked() -> None:
    dead = [k for k, v in _PAIRINGS.items() if v.expired or v.consumed]
    for k in dead:
        _PAIRINGS.pop(k, None)


def normalize_cookies(platform: str, raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize Chrome-style cookies into Playwright vault dicts."""
    spec = PLATFORM_COOKIE_SPEC.get(platform.lower())
    if spec is None:
        raise ValueError(f"Unsupported platform for quick connect: {platform}")
    default_domain = str(spec["default_domain"])
    allowed_names = {n.lower() for n in [*spec["required"], *spec["optional"]]}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if not name or not value:
            continue
        key = name.lower()
        # Keep platform allowlist, session* cookies, and common auth names; drop noise.
        if (
            key not in allowed_names
            and not key.startswith("session")
            and key not in {"li_at", "auth_token", "ct0", "sessionid", "csrftoken"}
        ):
            continue
        if key in seen:
            continue
        seen.add(key)
        domain = str(item.get("domain") or default_domain)
        path = str(item.get("path") or "/")
        cookie: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": domain,
            "path": path,
        }
        expires = item.get("expirationDate") or item.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            cookie["expires"] = float(expires)
        if "httpOnly" in item:
            cookie["httpOnly"] = bool(item["httpOnly"])
        if "secure" in item:
            cookie["secure"] = bool(item["secure"])
        out.append(cookie)

    required = [n.lower() for n in spec["required"]]
    have = {c["name"].lower() for c in out}
    missing = [n for n in required if n not in have]
    if missing:
        raise ValueError(
            f"Missing required cookie(s) for {platform}: {', '.join(missing)}. "
            "Open that site in Chrome, stay signed in, then click Connect in the extension."
        )
    return out


async def probe_session(platform: str, cookies: list[dict[str, Any]]) -> tuple[bool, str]:
    """Best-effort session check. Returns (ok, detail). Network errors → soft accept."""
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    headers = {"Cookie": cookie_header, "User-Agent": "RivalRadar/1.0"}
    try:
        if platform == "linkedin":
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                res = await client.get(
                    "https://www.linkedin.com/voyager/api/me",
                    headers={**headers, "csrf-token": "ajax:1"},
                )
            if res.status_code in {200, 201}:
                return True, "LinkedIn session verified"
            if res.status_code in {401, 403}:
                return False, "LinkedIn rejected the session cookie — sign in again in Chrome"
            return True, f"LinkedIn probe returned {res.status_code} — stored unverified"
        if platform == "x":
            ct0 = next((c["value"] for c in cookies if c["name"] == "ct0"), "")
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
                res = await client.get(
                    "https://api.x.com/1.1/account/verify_credentials.json",
                    headers={**headers, "x-csrf-token": ct0},
                )
            if res.status_code == 200:
                return True, "X session verified"
            if res.status_code in {401, 403}:
                return False, "X rejected the session — sign in again in Chrome"
            return True, f"X probe returned {res.status_code} — stored unverified"
        # Instagram / TikTok / Threads: accept after required cookies present.
        return True, f"{platform} cookies accepted (no live probe)"
    except Exception as exc:  # noqa: BLE001
        logger.info("quick-connect probe soft-fail for %s: %s", platform, exc)
        return True, f"{platform} cookies stored (probe unreachable)"
