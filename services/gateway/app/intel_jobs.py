"""Background Intel Brief jobs — start after Scout finishes, serve cached result."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.clients import generate_intel_report

logger = logging.getLogger(__name__)

_TTL_S = 6 * 3600
_lock = asyncio.Lock()
# cache_key → {status, report?, error?, updated_at, brand_name}
_jobs: dict[str, dict[str, Any]] = {}
_tasks: dict[str, asyncio.Task[None]] = {}


def _prune() -> None:
    now = time.time()
    dead = [k for k, v in _jobs.items() if now - float(v.get("updated_at") or 0) > _TTL_S]
    for k in dead:
        _jobs.pop(k, None)
        task = _tasks.pop(k, None)
        if task and not task.done():
            task.cancel()


async def get_intel_job(cache_key: str) -> dict[str, Any]:
    async with _lock:
        _prune()
        row = _jobs.get(cache_key)
        if not row:
            return {"cache_key": cache_key, "status": "miss"}
        out = {
            "cache_key": cache_key,
            "status": row.get("status") or "miss",
            "updated_at": row.get("updated_at"),
            "brand_name": row.get("brand_name"),
        }
        if row.get("status") == "done" and isinstance(row.get("report"), dict):
            out["report"] = row["report"]
        if row.get("status") == "error" and row.get("error"):
            out["error"] = row["error"]
        return out


async def start_intel_job(
    *,
    cache_key: str,
    body: dict[str, Any],
    operator_headers: dict[str, str],
    force: bool = False,
) -> dict[str, Any]:
    """Kick off (or return existing) intel generation for cache_key."""
    async with _lock:
        _prune()
        existing = _jobs.get(cache_key)
        if existing and not force:
            if existing.get("status") == "done" and existing.get("report"):
                return {
                    "cache_key": cache_key,
                    "status": "done",
                    "report": existing["report"],
                    "started": False,
                }
            if existing.get("status") == "running":
                return {"cache_key": cache_key, "status": "running", "started": False}

        _jobs[cache_key] = {
            "status": "running",
            "report": None,
            "error": None,
            "updated_at": time.time(),
            "brand_name": body.get("brand_name") or "the brand",
        }
        old = _tasks.pop(cache_key, None)
        if old and not old.done():
            old.cancel()
        _tasks[cache_key] = asyncio.create_task(
            _run_job(cache_key, body, operator_headers),
            name=f"intel-job-{cache_key[-12:]}",
        )
        return {"cache_key": cache_key, "status": "running", "started": True}


async def clear_intel_job(cache_key: str) -> None:
    async with _lock:
        _jobs.pop(cache_key, None)
        task = _tasks.pop(cache_key, None)
        if task and not task.done():
            task.cancel()


async def put_intel_report(cache_key: str, report: dict[str, Any], *, brand_name: str = "the brand") -> dict[str, Any]:
    """Store a finished report (e.g. from the live SSE path) so War Room remounts hit cache."""
    async with _lock:
        _prune()
        _jobs[cache_key] = {
            "status": "done",
            "report": report,
            "error": None,
            "updated_at": time.time(),
            "brand_name": brand_name,
        }
        task = _tasks.pop(cache_key, None)
        if task and not task.done():
            task.cancel()
        return {"cache_key": cache_key, "status": "done", "report": report}

async def _run_job(
    cache_key: str,
    body: dict[str, Any],
    operator_headers: dict[str, str],
) -> None:
    try:
        report = await generate_intel_report(body, operator_headers=operator_headers)
        async with _lock:
            _jobs[cache_key] = {
                "status": "done",
                "report": report,
                "error": None,
                "updated_at": time.time(),
                "brand_name": body.get("brand_name") or "the brand",
            }
        logger.info("intel job done key=%s", cache_key[-16:])
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None) or str(exc)
        if not isinstance(detail, str):
            detail = str(detail)
        logger.warning("intel job failed key=%s err=%s", cache_key[-16:], detail[:200])
        async with _lock:
            _jobs[cache_key] = {
                "status": "error",
                "report": None,
                "error": detail[:500],
                "updated_at": time.time(),
                "brand_name": body.get("brand_name") or "the brand",
            }
    finally:
        async with _lock:
            _tasks.pop(cache_key, None)
