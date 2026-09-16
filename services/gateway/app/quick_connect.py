"""Quick Connect — one-time pairing codes + cookie vault without noVNC."""

from __future__ import annotations

import logging
import secrets
import string
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

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
            "Open that site in your browser (Chrome or Comet), stay signed in, then click Connect."
        )
    return out


async def probe_session(platform: str, cookies: list[dict[str, Any]]) -> tuple[bool, str]:
    """Accept when required auth cookies exist; live probes are unreliable from datacenter IPs.

    LinkedIn/X often return 401/403 to server-side requests even with valid user cookies
    (IP reputation, CSRF checks, Comet/Chromium fingerprinting). So we do NOT reject on
    probe failure — the scout will surface auth issues at run time instead.
    """
    required = PLATFORM_COOKIE_SPEC.get(platform.lower(), {}).get("required", [])
    have = {c["name"].lower() for c in cookies}
    missing = [n.lower() for n in required if n.lower() not in have]
    if missing:
        return False, f"Missing auth cookie(s): {', '.join(missing)}"
    return True, f"{platform} session cookies accepted (verified at scout time)"
