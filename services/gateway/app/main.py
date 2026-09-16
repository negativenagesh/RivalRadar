from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.analytics import PageviewPayload, client_ip, geo_hints, insert_pageview
from app.config import cors_origin_list, settings
from app.db import init_models
from app.rate_limit import RateLimitMiddleware, visitor_id
from app.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    await init_models()
    yield


app = FastAPI(title="RivalRadar Gateway Service", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "gateway"}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Liveness for cold-start UI: gateway + generation + ingestion (Scout)."""
    generation_ok = False
    ingestion_ok = False
    detail = "generation unreachable"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{settings.generation_service_url.rstrip('/')}/health")
            generation_ok = response.status_code == 200
            detail = "ok" if generation_ok else f"generation status {response.status_code}"
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)[:160]
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(f"{settings.ingestion_service_url.rstrip('/')}/health")
            ingestion_ok = response.status_code == 200
            if generation_ok and not ingestion_ok:
                detail = f"ingestion status {response.status_code}"
    except Exception as exc:  # noqa: BLE001
        if generation_ok:
            detail = f"ingestion unreachable: {str(exc)[:120]}"
    ok = generation_ok and ingestion_ok
    body = {
        "status": "ok" if ok else "degraded",
        "gateway": "ok",
        "generation": "ok" if generation_ok else "down",
        "ingestion": "ok" if ingestion_ok else "down",
        "detail": detail if ok else detail,
        "mission_defaults": {
            "text": "gptoss",
            "image": "agnes",
        },
    }
    # Ready for Mission creative if generation is up; Scout needs ingestion too.
    # Return 200 when generation is up so cold-start UI clears; surface ingestion in body.
    return JSONResponse(body, status_code=200 if generation_ok else 503)


@app.post("/analytics/pageview")
async def analytics_pageview(payload: PageviewPayload, request: Request) -> dict[str, object]:
    headers = {k.lower(): v for k, v in request.headers.items()}
    geo = geo_hints(headers)
    ip = client_ip(headers, request.client.host if request.client else None)
    vid = getattr(request.state, "visitor_id", None) or visitor_id(request)
    row = {
        "visitor_id": vid,
        "visitor_token": payload.visitor_token,
        "path": payload.path,
        "referrer": payload.referrer,
        "title": payload.title,
        "language": payload.language,
        "timezone": payload.timezone,
        "screen_w": payload.screen_w,
        "screen_h": payload.screen_h,
        "viewport_w": payload.viewport_w,
        "viewport_h": payload.viewport_h,
        "platform": payload.platform,
        "user_agent": headers.get("user-agent"),
        "ip": ip,
        "country": geo["country"],
        "region": geo["region"],
        "city": geo["city"],
        "host": headers.get("host"),
    }
    stored = await insert_pageview(row)
    return {"ok": True, "stored": stored, "visitor_id": vid}
