"""Background intel job cache used after Scout finishes."""

from __future__ import annotations

import pytest
from app import intel_jobs


@pytest.fixture(autouse=True)
def _reset_jobs():
    intel_jobs._jobs.clear()
    intel_jobs._tasks.clear()
    yield
    intel_jobs._jobs.clear()
    for task in list(intel_jobs._tasks.values()):
        task.cancel()
    intel_jobs._tasks.clear()


@pytest.mark.asyncio
async def test_intel_job_stores_report(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_generate(body, *, operator_headers):  # noqa: ANN001
        assert body["brand_name"] == "Pixis"
        return {"markdown": "# Intel brief\n\n- hello", "narration": "agent", "reports": []}

    monkeypatch.setattr(intel_jobs, "generate_intel_report", _fake_generate)

    started = await intel_jobs.start_intel_job(
        cache_key="rivalradar.intel.test1",
        body={"facts": {"companies": []}, "brand_name": "Pixis"},
        operator_headers={},
    )
    assert started["status"] == "running"
    assert started["started"] is True

    task = intel_jobs._tasks["rivalradar.intel.test1"]
    await task

    done = await intel_jobs.get_intel_job("rivalradar.intel.test1")
    assert done["status"] == "done"
    assert "Intel brief" in done["report"]["markdown"]

    reuse = await intel_jobs.start_intel_job(
        cache_key="rivalradar.intel.test1",
        body={"facts": {}, "brand_name": "Pixis"},
        operator_headers={},
    )
    assert reuse["status"] == "done"
    assert reuse["started"] is False


@pytest.mark.asyncio
async def test_put_intel_report() -> None:
    out = await intel_jobs.put_intel_report(
        "rivalradar.intel.put",
        {"markdown": "# Cached\n", "narration": "agent"},
        brand_name="Acme",
    )
    assert out["status"] == "done"
    got = await intel_jobs.get_intel_job("rivalradar.intel.put")
    assert got["report"]["markdown"].startswith("# Cached")
