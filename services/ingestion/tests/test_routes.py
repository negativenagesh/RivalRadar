from httpx import AsyncClient


async def test_trigger_ingestion_endpoint(client: AsyncClient) -> None:
    response = await client.post("/ingest/run")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "accounts_ingested": 3,
        "posts_ingested": 10,
        "posts_skipped_duplicate": 0,
    }


async def test_list_accounts_and_posts_after_ingestion(client: AsyncClient) -> None:
    await client.post("/ingest/run")

    accounts_response = await client.get("/accounts")
    posts_response = await client.get("/posts")

    assert accounts_response.status_code == 200
    assert len(accounts_response.json()) == 3

    assert posts_response.status_code == 200
    posts = posts_response.json()
    assert len(posts) == 10
    assert all("engagement_score" in p for p in posts)
