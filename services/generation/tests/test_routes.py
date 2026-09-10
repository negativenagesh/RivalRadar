from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "generation"}


async def test_generate_draft_endpoint(client: AsyncClient) -> None:
    response = await client.post(
        "/drafts/generate",
        json={
            "cluster_format": "founder_post",
            "cluster_theme": "sustainability",
            "competitor_caption": "we planted trees",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["caption"] == "a generated caption"
    assert body["image_concept"] == "a generated image concept"
    assert len(body["voice_examples_used"]) == 3
    assert body["image_mime_type"] == "image/png"
    assert body["image_data_base64"]
