from app.connectors.fixture import FixtureConnector
from app.models import PostFormat


async def test_fetch_accounts_returns_fixture_data() -> None:
    connector = FixtureConnector()
    accounts = await connector.fetch_accounts()

    assert len(accounts) == 3
    assert {a["handle"] for a in accounts} == {"@nova.wear", "@brewbros", "@fitkit.co"}


async def test_fetch_posts_covers_all_formats() -> None:
    connector = FixtureConnector()
    posts = await connector.fetch_posts()

    assert len(posts) == 10
    formats = {p["format"] for p in posts}
    assert formats == {f.value for f in PostFormat}
