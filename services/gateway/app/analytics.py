"""Visitor / pageview tracking → Supabase (optional; no-op when unset)."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import settings

logger = logging.getLogger(__name__)


class PageviewPayload(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    referrer: str | None = Field(default=None, max_length=1000)
    title: str | None = Field(default=None, max_length=300)
    language: str | None = Field(default=None, max_length=40)
    timezone: str | None = Field(default=None, max_length=80)
    screen_w: int | None = Field(default=None, ge=0, le=10000)
    screen_h: int | None = Field(default=None, ge=0, le=10000)
    viewport_w: int | None = Field(default=None, ge=0, le=10000)
    viewport_h: int | None = Field(default=None, ge=0, le=10000)
    platform: str | None = Field(default=None, max_length=120)
    visitor_token: str | None = Field(default=None, max_length=64)


def client_ip(headers: dict[str, str], fallback: str | None) -> str:
    for key in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
        raw = headers.get(key)
        if raw and raw.strip():
            return raw.strip()
    forwarded = headers.get("x-forwarded-for") or ""
    parts = [p.strip() for p in forwarded.split(",") if p.strip()]
    if parts:
        return parts[-1]
    return fallback or "unknown"


def geo_hints(headers: dict[str, str]) -> dict[str, str | None]:
    return {
        "country": headers.get("cf-ipcountry")
        or headers.get("x-vercel-ip-country")
        or headers.get("cloudfront-viewer-country"),
        "region": headers.get("x-vercel-ip-country-region") or headers.get("x-region"),
        "city": headers.get("x-vercel-ip-city") or headers.get("x-city"),
    }


async def insert_pageview(row: dict[str, Any]) -> bool:
    """Insert into public.visitor_pageviews via Supabase REST. Returns False if skipped."""
    url = (settings.supabase_url or "").rstrip("/")
    key = settings.supabase_service_role_key or ""
    if not url or not key:
        logger.debug("supabase unset — skip pageview")
        return False
    endpoint = f"{url}/rest/v1/visitor_pageviews"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(endpoint, headers=headers, json=row)
            if response.status_code >= 400:
                logger.warning("supabase pageview failed: %s %s", response.status_code, response.text[:200])
                return False
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("supabase pageview error: %s", exc)
        return False
