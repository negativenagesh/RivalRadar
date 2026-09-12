"""Write Netscape HTTP Cookie File for gallery-dl / curl / yt-dlp."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any


def write_netscape_cookies(path: Path, cookies: list[dict[str, Any]]) -> Path:
    """Write Playwright-style cookies to a Netscape cookies.txt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Netscape HTTP Cookie File", "# RivalRadar connect-session export", ""]
    now = int(time.time())
    for raw in cookies:
        name = str(raw.get("name") or "").strip()
        if not name or raw.get("value") is None:
            continue
        value = str(raw["value"])
        domain = str(raw.get("domain") or "")
        if not domain and isinstance(raw.get("url"), str):
            from urllib.parse import urlparse

            host = urlparse(str(raw["url"])).hostname or ""
            domain = f".{host}" if host else ""
        if not domain:
            continue
        include_sub = "TRUE" if domain.startswith(".") else "FALSE"
        cookie_path = str(raw.get("path") or "/")
        expires = raw.get("expires")
        if isinstance(expires, (int, float)) and expires > 0:
            exp = str(int(expires))
        else:
            exp = str(now + 86400 * 30)
        secure = "TRUE" if raw.get("secure") else "FALSE"
        # Netscape: domain \t flag \t path \t secure \t expiration \t name \t value
        lines.append(
            "\t".join([domain, include_sub, cookie_path, secure, exp, name, value])
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def cookie_value(cookies: list[dict[str, Any]], name: str) -> str | None:
    for c in cookies:
        if str(c.get("name") or "") == name and c.get("value") is not None:
            return str(c["value"])
    return None
