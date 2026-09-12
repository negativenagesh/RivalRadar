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
    return out


def _normalize_cookies(raw: Any, *, default_domain: str) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        cookies: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict) and item.get("name") and item.get("value") is not None:
                cookie = {
                    "name": str(item["name"]),
                    "value": str(item["value"]),
                    "domain": str(item.get("domain") or default_domain),
                    "path": str(item.get("path") or "/"),
                }
                if item.get("url"):
                    cookie["url"] = str(item["url"])
                    cookie.pop("domain", None)
                cookies.append(cookie)
            elif isinstance(item, str) and "=" in item:
                name, value = item.split("=", 1)
                cookies.append(
                    {"name": name.strip(), "value": value.strip(), "domain": default_domain, "path": "/"}
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
        # Flat name→value map (excluding metadata keys)
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
