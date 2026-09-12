import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_and_upsert_connection(client: AsyncClient) -> None:
    listed = await client.get("/connections")
    assert listed.status_code == 200
    rows = listed.json()
    assert any(r["platform"] == "youtube" for r in rows)

    created = await client.post(
        "/connections/tiktok",
        json={
            "auth_type": "cookie",
            "secret": {"session": "opaque-cookie-bundle"},
            "scopes": ["read"],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["platform"] == "tiktok"
    assert body["status"] == "connected"

    # Passwords rejected
    bad = await client.post(
        "/connections/linkedin",
        json={"auth_type": "oauth", "secret": {"password": "nope"}},
    )
    assert bad.status_code == 400
