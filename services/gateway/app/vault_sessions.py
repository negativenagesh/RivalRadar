"""Load Connect-extension vault sessions for Scout (same source as /ingestion/runs)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlatformConnection
from app.vault import decrypt_json


async def load_vaulted_platform_sessions(
    session: AsyncSession,
    *,
    workspace_id: str = "default",
    platforms: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Decrypt Connect-extension blobs for connected platforms.

    This is the only cookie source Scout should use in production — the Chrome
    extension POSTs cookies via /connections/{platform}/quick into the vault.
    """
    rows = await session.scalars(
        select(PlatformConnection).where(
            PlatformConnection.workspace_id == workspace_id,
            PlatformConnection.status == "connected",
        )
    )
    out: dict[str, dict[str, Any]] = {}
    for row in rows.all():
        if platforms is not None and row.platform not in platforms:
            continue
        try:
            secret = decrypt_json(row.encrypted_blob)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(secret, dict):
            out[row.platform] = secret
    return out


def cookies_for_platform(
    platform_sessions: dict[str, dict[str, Any]], platform: str
) -> list[dict[str, Any]]:
    secret = platform_sessions.get(platform) or {}
    cookies = secret.get("cookies")
    if isinstance(cookies, list):
        return [c for c in cookies if isinstance(c, dict)]
    state = secret.get("storage_state")
    if isinstance(state, dict):
        nested = state.get("cookies")
        if isinstance(nested, list):
            return [c for c in nested if isinstance(c, dict)]
    return []
