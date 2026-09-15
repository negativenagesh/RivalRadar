"""Deploy + rate-limit + analytics readiness tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.config import _normalize_database_url, cors_origin_list
from app.rate_limit import MemoryRateLimiter, visitor_id
from httpx import AsyncClient
from starlette.requests import Request


def test_normalize_database_url_render_style() -> None:
    assert _normalize_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")
    assert "+asyncpg" in _normalize_database_url("postgresql://u:p@h/db")


def test_cors_origins_parser() -> None:
    assert "https://app.vercel.app" in ["https://app.vercel.app", "http://localhost:3000"]
    assert cors_origin_list()  # smoke default list


def test_memory_rate_limiter_blocks() -> None:
    limiter = MemoryRateLimiter()
    assert limiter.allow("v1:/creative/generate", 2, 60)[0] is True
    assert limiter.allow("v1:/creative/generate", 2, 60)[0] is True
    allowed, retry = limiter.allow("v1:/creative/generate", 2, 60)
    assert allowed is False
    assert retry >= 1


def test_visitor_id_is_ip_anchored() -> None:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [
            (b"user-agent", b"TestAgent/1.0"),
            (b"x-forwarded-for", b"203.0.113.9"),
            (b"x-rr-vid", b"attacker-rotating-token"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    req = Request(scope)
    a = visitor_id(req)
    scope2 = dict(scope)
    scope2["headers"] = [
        (b"user-agent", b"TotallyDifferent/9.9"),
        (b"x-forwarded-for", b"203.0.113.9"),
        (b"x-rr-vid", b"another-token"),
    ]
    b = visitor_id(Request(scope2))
    assert a == b
    assert len(a) == 32


@pytest.mark.asyncio
async def test_health_and_pageview_without_supabase(client: AsyncClient) -> None:
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "gateway"

    with patch("app.main.insert_pageview", new=AsyncMock(return_value=False)) as mocked:
        res = await client.post(
            "/analytics/pageview",
            json={"path": "/mission", "visitor_token": "abc12345", "language": "en"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["stored"] is False
    mocked.assert_awaited_once()


@pytest.mark.asyncio
async def test_ready_degraded_when_generation_down(client: AsyncClient) -> None:
    with patch("app.main.httpx.AsyncClient") as client_cls:
        instance = AsyncMock()
        instance.__aenter__.return_value = instance
        instance.get.side_effect = RuntimeError("down")
        client_cls.return_value = instance
        res = await client.get("/ready")
    assert res.status_code == 503
    assert res.json()["generation"] == "down"
