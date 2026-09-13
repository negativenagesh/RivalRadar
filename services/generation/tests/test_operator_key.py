from app.main import app
from app.routes import operator_provider
from httpx import ASGITransport, AsyncClient

from llm_provider import get_llm_provider


async def test_mission_llm_requires_gemini_header() -> None:
    app.dependency_overrides.pop(operator_provider, None)
    app.dependency_overrides.pop(get_llm_provider, None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        creative = await client.post(
            "/creative/generate",
            json={"kind": "comment", "brand_name": "Pixis"},
        )
        assert creative.status_code == 400
        assert "Gemini" in creative.json()["detail"]

        intel = await client.post("/intel/report", json={"facts": {}, "brand_name": "Pixis"})
        assert intel.status_code == 400
        assert "Gemini" in intel.json()["detail"]
