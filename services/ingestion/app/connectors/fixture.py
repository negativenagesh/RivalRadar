import json
from importlib.resources import files
from typing import cast

from app.connectors.base import RawAccount, RawPost


class FixtureConnector:
    """Connector backed by static fixture JSON, standing in for a real
    scraper/paid-API integration until one is built.
    """

    def __init__(self, fixtures_package: str = "app.fixtures") -> None:
        self._fixtures = files(fixtures_package)

    async def fetch_accounts(self) -> list[RawAccount]:
        data = json.loads((self._fixtures / "accounts.json").read_text())
        return cast(list[RawAccount], data)

    async def fetch_posts(self) -> list[RawPost]:
        data = json.loads((self._fixtures / "posts.json").read_text())
        return cast(list[RawPost], data)
