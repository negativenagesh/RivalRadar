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
