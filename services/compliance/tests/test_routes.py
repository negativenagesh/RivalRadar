from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "compliance"}


async def test_check_compliance_endpoint_passes_clean_text(client: AsyncClient) -> None:
    response = await client.post("/compliance/check", json={"text": "a clean on-brand caption"})

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is True
    assert body["rule_violations"] == []


async def test_check_compliance_endpoint_flags_banned_claim(client: AsyncClient) -> None:
    response = await client.post("/compliance/check", json={"text": "guaranteed results overnight"})

    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert len(body["rule_violations"]) > 0
