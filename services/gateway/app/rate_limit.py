"""Per-visitor rate limits for public deploy (Render free + shared NVIDIA/Agnes keys)."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

# Conservative quotas so shared gpt-oss + Agnes keys survive multi-tenant traffic.
# Buckets are per visitor fingerprint (IP + UA + optional rr_vid cookie).
LIMITS: dict[str, tuple[int, int]] = {
    # path prefix → (max_requests, window_seconds)
    "/creative/generate": (20, 3600),
    "/creative/publish-plan": (30, 3600),
    "/intel/report": (15, 3600),
    "/social/stage-post": (15, 3600),
    "/social/comment": (20, 3600),
    "/ingestion/runs": (10, 3600),
    "/pipeline/runs": (8, 3600),
    "/connect/": (30, 3600),
    "/analytics/": (240, 3600),
    "*": (180, 3600),
}

_SKIP_PREFIXES = ("/health", "/ready", "/docs", "/openapi", "/redoc")


def visitor_id(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    ua = request.headers.get("user-agent") or ""
    vid = request.cookies.get("rr_vid") or request.headers.get("x-rr-vid") or ""
    raw = f"{ip}|{ua}|{vid}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _match_limit(path: str) -> tuple[str, int, int]:
    for prefix, (max_req, window) in LIMITS.items():
        if prefix != "*" and path.startswith(prefix):
            return prefix, max_req, window
    max_req, window = LIMITS["*"]
    return "*", max_req, window


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._hits[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= max_requests:
                retry = max(1, int(window_seconds - (now - q[0])))
                return False, retry
            q.append(now)
            return True, 0


_limiter = MemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or any(path.startswith(p) for p in _SKIP_PREFIXES):
            return await call_next(request)

        bucket, max_req, window = _match_limit(path)
        vid = visitor_id(request)
        request.state.visitor_id = vid
        allowed, retry_after = _limiter.allow(f"{vid}:{bucket}", max_req, window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit for this visitor on {bucket}: "
                        f"{max_req} requests / {window // 60} min. Try again soon."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Bucket"] = bucket
        response.headers["X-Visitor-Id"] = vid
        return response
