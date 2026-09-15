import json
from collections.abc import AsyncIterator
from typing import Any, NoReturn

import httpx
from fastapi import HTTPException

from app.config import settings

GEMINI_MISSING = (
    "Paste a key in the Models chip, or set NVIDIA_API_KEY / AGNES_API_KEY / "
    "GEMINI_API_KEY in the server .env (defaults: gpt-oss text, Agnes image)."
)


async def fetch_model_defaults() -> dict[str, Any]:
    """Server-env Mission model defaults (gpt-oss / Agnes) from generation."""
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=10.0) as client:
        try:
            response = await client.get("/models/defaults")
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError):
            return {"text_model": None, "image_model": None, "available": False, "source": "server-env"}
        result: dict[str, Any] = response.json()
        return result


def _reraise_upstream(exc: httpx.HTTPStatusError) -> NoReturn:
    detail: object = f"upstream {exc.response.status_code}"
    try:
        data = exc.response.json()
        if isinstance(data, dict) and "detail" in data:
            detail = data["detail"]
    except Exception:  # noqa: BLE001
        text = (exc.response.text or "")[:400]
        if text:
            detail = text
    raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc


async def fetch_latest_digest() -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.intelligence_service_url, timeout=10.0) as client:
        response = await client.get("/digests/latest")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def trigger_digest_generation() -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.intelligence_service_url, timeout=30.0) as client:
        response = await client.post("/digests/generate")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def generate_draft_content(
    *, cluster_format: str, cluster_theme: str, competitor_caption: str
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=30.0) as client:
        response = await client.post(
            "/drafts/generate",
            json={
                "cluster_format": cluster_format,
                "cluster_theme": cluster_theme,
                "competitor_caption": competitor_caption,
            },
        )
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


def _reraise_transport(exc: httpx.RequestError) -> NoReturn:
    raise HTTPException(
        status_code=502,
        detail=f"generation service unreachable ({exc.__class__.__name__})",
    ) from exc


async def generate_creative_content(
    body: dict[str, Any], *, operator_headers: dict[str, str]
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=180.0) as client:
        try:
            response = await client.post(
                "/creative/generate",
                json=body,
                headers=operator_headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        except httpx.RequestError as exc:
            _reraise_transport(exc)
        result: dict[str, Any] = response.json()
        return result


async def generate_intel_report(
    body: dict[str, Any], *, operator_headers: dict[str, str]
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=240.0) as client:
        try:
            response = await client.post(
                "/intel/report",
                json=body,
                headers=operator_headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        except httpx.RequestError as exc:
            _reraise_transport(exc)
        result: dict[str, Any] = response.json()
        return result


async def stream_intel_report(
    body: dict[str, Any], *, operator_headers: dict[str, str]
) -> AsyncIterator[str]:
    """Proxy generation's intel SSE stream byte-for-byte."""
    try:
        async with httpx.AsyncClient(
            base_url=settings.generation_service_url, timeout=httpx.Timeout(300.0, read=300.0)
        ) as client, client.stream(
            "POST", "/intel/report/stream", json=body, headers=operator_headers
        ) as response:
            if response.status_code != 200:
                await response.aread()
                detail = response.text[:400]
                try:
                    payload = response.json()
                    detail = str(payload.get("detail") or detail)
                except Exception:  # noqa: BLE001
                    pass
                yield f"event: error\ndata: {json.dumps({'detail': detail})}\n\n"
                return
            async for chunk in response.aiter_text():
                yield chunk
    except httpx.RequestError as exc:
        detail = f"generation service unreachable ({exc.__class__.__name__})"
        yield f"event: error\ndata: {json.dumps({'detail': detail})}\n\n"


async def ping_generation_vendor(
    body: dict[str, Any], *, operator_headers: dict[str, str]
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=90.0) as client:
        try:
            response = await client.post("/llm/ping", json=body, headers=operator_headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        except httpx.RequestError as exc:
            _reraise_transport(exc)
        result: dict[str, Any] = response.json()
        return result


async def drop_ingestion_comment(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=120.0) as client:
        try:
            response = await client.post("/social/comment", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        result: dict[str, Any] = response.json()
        return result


async def generate_publish_plan(
    body: dict[str, Any], *, operator_headers: dict[str, str]
) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=120.0) as client:
        try:
            response = await client.post(
                "/creative/publish-plan", json=body, headers=operator_headers
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        except httpx.RequestError as exc:
            _reraise_transport(exc)
        result: dict[str, Any] = response.json()
        return result


async def stage_ingestion_post(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=180.0) as client:
        try:
            response = await client.post("/social/stage-post", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _reraise_upstream(exc)
        except httpx.RequestError as exc:
            _reraise_transport(exc)
        result: dict[str, Any] = response.json()
        return result


async def check_compliance(text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.compliance_service_url, timeout=30.0) as client:
        response = await client.post("/compliance/check", json={"text": text})
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def trigger_ingestion_run(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=30.0) as client:
        response = await client.post("/ingest/run", json=body)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def fetch_ingestion_run(run_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=10.0) as client:
        response = await client.get(f"/ingest/runs/{run_id}")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def cancel_ingestion_run(run_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=15.0) as client:
        response = await client.post(f"/ingest/runs/{run_id}/cancel")
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def fetch_ingestion_posts() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=10.0) as client:
        response = await client.get("/posts")
        response.raise_for_status()
        result: list[dict[str, Any]] = response.json()
        return result


async def fetch_ingestion_accounts() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=10.0) as client:
        response = await client.get("/accounts")
        response.raise_for_status()
        result: list[dict[str, Any]] = response.json()
        return result


async def fetch_ingestion_recording(run_id: str) -> httpx.Response:
    """Return the raw streaming response from ingestion (caller must close)."""
    client = httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=60.0)
    request = client.build_request("GET", f"/ingest/runs/{run_id}/recording")
    response = await client.send(request, stream=True)
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        response.raise_for_status()
    response.extensions["rivalradar_client"] = client
    return response


async def fetch_ingestion_screenshot(run_id: str, index: int) -> httpx.Response:
    client = httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=30.0)
    request = client.build_request("GET", f"/ingest/runs/{run_id}/screenshots/{index}")
    response = await client.send(request, stream=True)
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        response.raise_for_status()
    response.extensions["rivalradar_client"] = client
    return response



async def fetch_youtube_status() -> dict[str, object]:
    async with httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=10.0) as client:
        response = await client.get("/youtube/status")
        response.raise_for_status()
        result: dict[str, object] = response.json()
        return result


async def fetch_ingestion_media(media_key: str) -> httpx.Response:
    client = httpx.AsyncClient(base_url=settings.ingestion_service_url, timeout=30.0)
    request = client.build_request("GET", f"/media/{media_key}")
    response = await client.send(request, stream=True)
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        response.raise_for_status()
    response.extensions["rivalradar_client"] = client
    return response
