"""Deploy + rate-limit + analytics readiness tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.config import _host_needs_ssl, _normalize_database_url, cors_origin_list
from app.rate_limit import MemoryRateLimiter, visitor_id
from httpx import AsyncClient
from starlette.requests import Request


def test_normalize_database_url_render_style() -> None:
    assert _normalize_database_url("postgres://u:p@h/db").startswith("postgresql+asyncpg://")
    assert "+asyncpg" in _normalize_database_url("postgresql://u:p@h/db")
    cleaned = _normalize_database_url("postgresql://u:p@dpg-x/db?sslmode=require")
    assert "sslmode" not in cleaned
    assert cleaned.startswith("postgresql+asyncpg://")


def test_cors_origins_parser() -> None:
    assert "https://app.vercel.app" in ["https://app.vercel.app", "http://localhost:3000"]
    assert cors_origin_list()  # smoke default list


def test_host_needs_ssl() -> None:
    assert _host_needs_ssl("postgresql+asyncpg://u:p@dpg-abc/db") is True
    assert _host_needs_ssl("postgresql+asyncpg://u:p@localhost/db") is False
    assert _host_needs_ssl("postgresql+asyncpg://u:p@postgres:5432/db") is False


def test_database_ssl_connect_arg_is_require_mode() -> None:
    """Render self-signed TLS needs asyncpg ssl='require', not ssl=True (verify)."""
    from app import db as db_mod
    from app.config import settings

    if settings.database_ssl:
        assert db_mod._connect_args.get("ssl") == "require"
    else:
        assert "ssl" not in db_mod._connect_args


def test_memory_rate_limiter_blocks() -> None:
    limiter = MemoryRateLimiter()
    assert limiter.allow("v1:/creative/generate", 2, 60)[0] is True
    assert limiter.allow("v1:/creative/generate", 2, 60)[0] is True
    allowed, retry = limiter.allow("v1:/creative/generate", 2, 60)
    assert allowed is False
    assert retry >= 1


def test_visitor_id_ignores_spoofed_xff_prefix() -> None:
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
            (b"x-forwarded-for", b"198.51.100.1, 203.0.113.9"),
        ],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    # Rightmost hop wins when no CF / X-Real-IP header is present.
    assert visitor_id(Request(scope)) == visitor_id(
        Request(
            {
                **scope,
                "headers": [(b"x-forwarded-for", b"203.0.113.9")],
            }
        )
    )

    # CF-Connecting-IP beats a spoofed XFF chain.
    with_cf = Request(
        {
            **scope,
            "headers": [
                (b"cf-connecting-ip", b"203.0.113.9"),
                (b"x-forwarded-for", b"198.51.100.1, 203.0.113.9"),
            ],
        }
    )
    spoofed = Request(
        {
            **scope,
            "headers": [
                (b"cf-connecting-ip", b"203.0.113.9"),
                (b"x-forwarded-for", b"1.2.3.4, 203.0.113.9"),
            ],
        }
    )
    assert visitor_id(with_cf) == visitor_id(spoofed)


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


@pytest.mark.asyncio
async def test_start_ingestion_returns_503_when_unreachable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def raise_503(_body: dict[str, object]) -> dict[str, object]:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Scout (ingestion) is unreachable")

    monkeypatch.setattr("app.routes.trigger_ingestion_run", raise_503)
    res = await client.post("/ingestion/runs", json={"targets": []})
    assert res.status_code == 503
    assert "unreachable" in res.json()["detail"].lower()
