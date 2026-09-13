import asyncio
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _wait_for_run_done(client: AsyncClient, run_id: str) -> dict[str, Any]:
    for _ in range(50):
        response = await client.get(f"/ingest/runs/{run_id}")
        body: dict[str, Any] = response.json()
        if body["status"] in ("done", "error", "cancelled"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish in time")


async def test_trigger_ingestion_endpoint(client: AsyncClient) -> None:
    response = await client.post("/ingest/run", json={"connector": "fixture"})

    assert response.status_code == 202
    run_id = response.json()["run_id"]

    run = await _wait_for_run_done(client, run_id)
    assert run["status"] == "done"
    result = run["result"]
    assert result["accounts_ingested"] == 3
    assert result["posts_ingested"] == 10
    assert result["posts_skipped_duplicate"] == 0
    assert result["lookback_days"] == 3
    assert result["sources_used"] == []
    assert result["screenshots"] == []
    assert "date_from" in result and "date_to" in result


async def test_cancel_ingestion_run(client: AsyncClient, session: AsyncSession) -> None:
    from app.models import IngestionRun, RunStatus

    stuck = IngestionRun(
        id="00000000-0000-4000-8000-000000000099",
        connector_type="fixture",
        status=RunStatus.RUNNING,
        record=False,
    )
    session.add(stuck)
    await session.commit()

    cancel = await client.post(f"/ingest/runs/{stuck.id}/cancel")
    assert cancel.status_code == 200
    body = cancel.json()
    assert body["id"] == stuck.id
    assert body["status"] == "cancelled"
    assert body["error_detail"] == "cancelled by operator"

    # Idempotent on terminal runs
    again = await client.post(f"/ingest/runs/{stuck.id}/cancel")
    assert again.status_code == 200
    assert again.json()["status"] == "cancelled"


async def test_cancel_missing_run(client: AsyncClient) -> None:
    response = await client.post("/ingest/runs/does-not-exist/cancel")
    assert response.status_code == 404


async def test_list_accounts_and_posts_after_ingestion(client: AsyncClient) -> None:
    response = await client.post("/ingest/run", json={"connector": "fixture"})
    await _wait_for_run_done(client, response.json()["run_id"])

    accounts_response = await client.get("/accounts")
    posts_response = await client.get("/posts")

    assert accounts_response.status_code == 200
    assert len(accounts_response.json()) == 3

    assert posts_response.status_code == 200
    posts = posts_response.json()
    assert len(posts) == 10
    assert all("engagement_score" in p for p in posts)


async def test_social_comment_requires_approval(client: AsyncClient) -> None:
    response = await client.post(
        "/social/comment",
        json={
            "platform": "linkedin",
            "url": "https://www.linkedin.com/feed/update/urn:li:activity:1",
            "text": "sharp take",
            "approved": False,
        },
    )
    assert response.status_code == 400
    assert "approval" in response.json()["detail"]
