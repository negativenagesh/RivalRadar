from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.fixtures import make_post


async def test_get_latest_digest_returns_404_when_none_exist(client: AsyncClient) -> None:
    response = await client.get("/digests/latest")
    assert response.status_code == 404


async def test_trigger_digest_generation(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    posts = [make_post("p1"), make_post("p2", format="founder_post", themes=["founder"])]
    monkeypatch.setattr("app.routes.fetch_posts", AsyncMock(return_value=posts))

    response = await client.post("/digests/generate")

    assert response.status_code == 200
    body = response.json()
    assert body["post_count"] == 2
    assert len(body["clusters"]) == 2


async def test_get_latest_digest_after_generation(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    posts = [make_post("p1")]
    monkeypatch.setattr("app.routes.fetch_posts", AsyncMock(return_value=posts))

    await client.post("/digests/generate")
    response = await client.get("/digests/latest")

    assert response.status_code == 200
    assert response.json()["post_count"] == 1


async def test_list_digests_returns_all_generated(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routes.fetch_posts", AsyncMock(return_value=[make_post("p1")]))

    await client.post("/digests/generate")
    await client.post("/digests/generate")
    response = await client.get("/digests")

    assert response.status_code == 200
    assert len(response.json()) == 2
