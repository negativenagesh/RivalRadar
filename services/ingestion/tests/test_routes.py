import asyncio
from typing import Any

from httpx import AsyncClient


async def _wait_for_run_done(client: AsyncClient, run_id: str) -> dict[str, Any]:
    for _ in range(50):
        response = await client.get(f"/ingest/runs/{run_id}")
        body: dict[str, Any] = response.json()
        if body["status"] in ("done", "error"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError(f"run {run_id} did not finish in time")


async def test_trigger_ingestion_endpoint(client: AsyncClient) -> None:
    response = await client.post("/ingest/run", json={"connector": "fixture"})

    assert response.status_code == 202
    run_id = response.json()["run_id"]

    run = await _wait_for_run_done(client, run_id)
    assert run["status"] == "done"
    assert run["result"] == {
        "accounts_ingested": 3,
        "posts_ingested": 10,
        "posts_skipped_duplicate": 0,
        "lookback_days": 3,
        "sources_used": [],
        "screenshots": [],
    }


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
