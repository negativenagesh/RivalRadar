import asyncio

import pytest
from app.connectors.composite import CompositeConnector


class _Slow:
    def __init__(self, name: str, delay: float) -> None:
        self.name = name
        self.delay = delay
        self.started_at: float | None = None
        self.sources_used = [name]

    async def fetch_accounts(self) -> list[dict[str, str]]:
        loop = asyncio.get_running_loop()
        self.started_at = loop.time()
        await asyncio.sleep(self.delay)
        return [{"handle": self.name, "display_name": self.name, "platform": self.name}]

    async def fetch_posts(self) -> list[dict[str, object]]:
        return []

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_composite_runs_connectors_concurrently() -> None:
    a = _Slow("youtube", 0.15)
    b = _Slow("browser", 0.15)
    composite = CompositeConnector([a, b])
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    accounts = await composite.fetch_accounts()
    elapsed = loop.time() - t0
    assert len(accounts) == 2
    assert a.started_at is not None and b.started_at is not None
    assert abs(a.started_at - b.started_at) < 0.05
    assert elapsed < 0.28
