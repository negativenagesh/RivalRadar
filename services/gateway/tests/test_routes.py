import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from tests.fixtures import make_compliance_response, make_digest, make_generation_response


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "gateway"}


async def test_get_latest_digest_proxies_intelligence_service(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routes.fetch_latest_digest", AsyncMock(return_value=make_digest()))

    response = await client.get("/digest/latest")

    assert response.status_code == 200
    assert response.json()["id"] == "digest-1"


async def _wait_for_pipeline_run_done(client: AsyncClient, run_id: str) -> dict[str, object]:
    for _ in range(50):
        response = await client.get(f"/pipeline-runs/{run_id}")
        body: dict[str, object] = response.json()
        if body["status"] in ("done", "error"):
            return body
        await asyncio.sleep(0.02)
    raise AssertionError(f"pipeline run {run_id} did not finish in time")


async def _generate_one_draft(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr("app.runs.fetch_latest_digest", AsyncMock(return_value=make_digest()))
    monkeypatch.setattr(
        "app.pipeline.generate_draft_content", AsyncMock(return_value=make_generation_response())
    )
    monkeypatch.setattr(
        "app.pipeline.check_compliance", AsyncMock(return_value=make_compliance_response())
    )

    response = await client.post("/drafts/generate")
    assert response.status_code == 202
    run = await _wait_for_pipeline_run_done(client, response.json()["run_id"])
    assert run["status"] == "done"
    draft_id: str = run["draft_ids"][0]  # type: ignore[index]
    return draft_id


async def test_generate_and_list_drafts(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    await _generate_one_draft(client, monkeypatch)

    response = await client.get("/drafts")

    assert response.status_code == 200
    drafts = response.json()
    assert len(drafts) == 1
    assert drafts[0]["review_state"] == "pending"
    assert drafts[0]["final_caption"] == drafts[0]["caption"]
    assert drafts[0]["image_mime_type"] == "image/png"
    assert drafts[0]["image_data_base64"]


async def test_approve_draft_marks_ready_to_publish(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_id = await _generate_one_draft(client, monkeypatch)

    response = await client.post(f"/drafts/{draft_id}/approve")

    assert response.status_code == 200
    assert response.json()["review_state"] == "ready_to_publish"


async def test_approve_ignores_compliance_failure_reviewer_can_override(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.runs.fetch_latest_digest", AsyncMock(return_value=make_digest()))
    monkeypatch.setattr(
        "app.pipeline.generate_draft_content", AsyncMock(return_value=make_generation_response())
    )
    monkeypatch.setattr(
        "app.pipeline.check_compliance",
        AsyncMock(return_value=make_compliance_response(passed=False)),
    )
    generate_response = await client.post("/drafts/generate")
    run = await _wait_for_pipeline_run_done(client, generate_response.json()["run_id"])
    draft_id = run["draft_ids"][0]  # type: ignore[index]

    drafts_response = await client.get("/drafts")
    assert drafts_response.json()[0]["compliance_passed"] is False

    response = await client.post(f"/drafts/{draft_id}/approve")

    assert response.status_code == 200
    assert response.json()["review_state"] == "ready_to_publish"


async def test_edit_draft_sets_edited_caption_and_state(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_id = await _generate_one_draft(client, monkeypatch)

    response = await client.post(f"/drafts/{draft_id}/edit", json={"caption": "a better caption"})

    assert response.status_code == 200
    body = response.json()
    assert body["review_state"] == "edited"
    assert body["edited_caption"] == "a better caption"
    assert body["final_caption"] == "a better caption"


async def test_reject_draft_sets_rejected_state(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft_id = await _generate_one_draft(client, monkeypatch)

    response = await client.post(f"/drafts/{draft_id}/reject")

    assert response.status_code == 200
    assert response.json()["review_state"] == "rejected"


async def test_approve_nonexistent_draft_returns_404(client: AsyncClient) -> None:
    response = await client.post("/drafts/does-not-exist/approve")
    assert response.status_code == 404
