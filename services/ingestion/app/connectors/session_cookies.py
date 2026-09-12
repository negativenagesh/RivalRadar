"""Normalize vaulted Connect-session secrets into Playwright cookie dicts."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_PLATFORM_DOMAINS: dict[str, str] = {
    "linkedin": ".linkedin.com",
    "x": ".x.com",
    "twitter": ".x.com",
    "instagram": ".instagram.com",
    "tiktok": ".tiktok.com",
    "threads": ".threads.net",
    "facebook": ".facebook.com",
    "meta": ".facebook.com",
}

_SAMESITE_MAP = {
    "strict": "Strict",
    "lax": "Lax",
    "none": "None",
    "no_restriction": "None",
    "unspecified": "Lax",
}


def cookies_from_sessions(
    platform_sessions: dict[str, Any],
    *,
    platforms: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Flatten platform_sessions secrets into Playwright add_cookies payloads."""
    out: list[dict[str, Any]] = []
    for platform, secret in platform_sessions.items():
        key = platform.lower()
        if platforms is not None and key not in platforms:
            continue
        if not isinstance(secret, dict):
            continue
        default_domain = _PLATFORM_DOMAINS.get(key, f".{key}.com")
        raw = secret.get("cookies", secret)
        out.extend(_normalize_cookies(raw, default_domain=default_domain))
        state = secret.get("storage_state")
        if isinstance(state, dict):
            state_cookies = state.get("cookies")
            if isinstance(state_cookies, list):
                out.extend(_normalize_cookies(state_cookies, default_domain=default_domain))
    return sanitize_playwright_cookies(out)


def storage_state_from_sessions(
    platform_sessions: dict[str, Any],
    *,
    platforms: set[str] | None = None,
) -> dict[str, Any] | None:
    """Return a single Playwright storage_state when exactly one platform has one.

    Multi-platform scouts rely on flattened cookies instead.
    """
    found: list[dict[str, Any]] = []
    for platform, secret in platform_sessions.items():
        key = platform.lower()
        if platforms is not None and key not in platforms:
            continue
        if not isinstance(secret, dict):
            continue
        state = secret.get("storage_state")
        if isinstance(state, dict) and state:
            found.append(state)
    if len(found) == 1:
        return found[0]
    return None


def sanitize_playwright_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop / repair fields that make Chromium Storage.setCookies fail."""
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in cookies:
        item = _sanitize_one(raw)
        if item is None:
            continue
        key = (item["name"], str(item.get("domain") or item.get("url") or ""), str(item.get("path") or "/"))
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _sanitize_one(raw: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw.get("name") or "").strip()
    if not name or raw.get("value") is None:
        return None
    value = str(raw["value"])
    cookie: dict[str, Any] = {"name": name, "value": value}

    url = raw.get("url")
    domain = raw.get("domain")
    path = str(raw.get("path") or "/")

    if isinstance(url, str) and url.startswith(("http://", "https://")):
        # Prefer url-only form — avoids domain/path mismatches from dumps.
        cookie["url"] = url.split("#", 1)[0]
    elif isinstance(domain, str) and domain.strip():
        d = domain.strip()
        # Chromium rejects bare hostnames without a path.
        cookie["domain"] = d
        cookie["path"] = path if path.startswith("/") else f"/{path}"
    else:
        return None

    expires = raw.get("expires")
    if isinstance(expires, (int, float)) and expires > 0:
        cookie["expires"] = float(expires)

    if "httpOnly" in raw:
        cookie["httpOnly"] = bool(raw["httpOnly"])
    if "secure" in raw:
        cookie["secure"] = bool(raw["secure"])

    same = raw.get("sameSite")
    if isinstance(same, str) and same.strip():
        mapped = _SAMESITE_MAP.get(same.strip().lower(), same.strip())
        if mapped in {"Strict", "Lax", "None"}:
            cookie["sameSite"] = mapped
            if mapped == "None":
                cookie["secure"] = True

    # Session cookies from dumps sometimes set expires=-1; omit entirely.
    return cookie


def _normalize_cookies(raw: Any, *, default_domain: str) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        cookies: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                cookies.append(dict(item))
            elif isinstance(item, str) and "=" in item:
                name, value = item.split("=", 1)
                cookies.append(
                    {
                        "name": name.strip(),
                        "value": value.strip(),
                        "domain": default_domain,
                        "path": "/",
                    }
                )
        return cookies
    if isinstance(raw, str) and "=" in raw:
        cookies = []
        for part in raw.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            cookies.append(
                {
                    "name": name.strip(),
                    "value": value.strip(),
                    "domain": default_domain,
                    "path": "/",
                }
            )
        return cookies
    if isinstance(raw, dict):
        skip = {"cookies", "note", "oauth_placeholder", "source", "auth_type"}
        cookies = []
        for name, value in raw.items():
            if name in skip or value is None:
                continue
            if isinstance(value, (dict, list)):
                continue
            cookies.append(
                {"name": str(name), "value": str(value), "domain": default_domain, "path": "/"}
            )
        return cookies
    return []


def domain_hint_from_url(url: str) -> str | None:
    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return None
    if not host:
        return None
    parts = host.split(".")
    if len(parts) >= 2:
        return "." + ".".join(parts[-2:])
    return host
