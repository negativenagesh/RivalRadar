from typing import Any

import httpx

from app.config import settings


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


async def generate_creative_content(body: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=settings.generation_service_url, timeout=90.0) as client:
        response = await client.post("/creative/generate", json=body)
        response.raise_for_status()
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
    # Attach client so the route can close both after streaming.
    response.extensions["rivalradar_client"] = client
    return response
