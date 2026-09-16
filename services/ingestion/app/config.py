from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Render/Neon hand postgres:// — SQLAlchemy async needs postgresql+asyncpg://."""
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")

    parts = urlsplit(url)
    if not parts.query:
        return url
    drop = {"sslmode", "ssl", "channel_binding"}
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in drop
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


def _host_needs_ssl(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host not in {"", "localhost", "127.0.0.1", "postgres"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rivalradar:rivalradar@localhost:5432/rivalradar"
    # Empty / "memory" → in-process FakeRedis (Scout starts without Upstash on free tier).
    redis_url: str = "memory"
    object_store_root: str = "/data/objects"
    browser_headless: bool = True
    youtube_api_key: str | None = None

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value

    @property
    def database_ssl(self) -> bool:
        return _host_needs_ssl(self.database_url)


settings = Settings()
