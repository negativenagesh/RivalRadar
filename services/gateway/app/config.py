from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Render/Neon hand postgres:// — SQLAlchemy async needs postgresql+asyncpg://.

    Also strip libpq-only query keys (sslmode, channel_binding) that break asyncpg
    when passed through SQLAlchemy's URL query → connect kwargs.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url.removeprefix("postgres://")
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = "postgresql+asyncpg://" + url.removeprefix("postgresql://")

    parts = urlsplit(url)
    if not parts.query:
        return url
    drop = {"sslmode", "ssl", "channel_binding"}
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in drop]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment))


def _host_needs_ssl(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return host not in {"", "localhost", "127.0.0.1", "postgres"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rivalradar:rivalradar@localhost:5432/rivalradar"
    # Empty / "memory" → in-process FakeRedis (Mission works without Upstash on free tier).
    redis_url: str = "memory"
    ingestion_service_url: str = "http://localhost:8001"
    intelligence_service_url: str = "http://localhost:8002"
    generation_service_url: str = "http://localhost:8003"
    compliance_service_url: str = "http://localhost:8004"
    connection_vault_key: str | None = None
    # Compose service by default; override to host.docker.internal:8765 for native host agent.
    connect_agent_url: str = "http://connect-agent:8765"
    # Browser-facing noVNC URL (host localhost, not the docker DNS name).
    connect_viewer_url: str = "http://localhost:7900/vnc.html?autoconnect=1&resize=scale"
    # Comma-separated browser origins for CORS (Vercel + local). Empty → localhost defaults.
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Optional Supabase visitor analytics (service role — never expose to browser).
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    # When true, never load social session cookies from process env — users sign in via Connect.
    disallow_env_social_cookies: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def _db_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_database_url(value)
        return value

    @field_validator("connect_agent_url", mode="before")
    @classmethod
    def _blank_agent_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "http://connect-agent:8765"
        return value

    @field_validator("connect_viewer_url", mode="before")
    @classmethod
    def _blank_viewer_url(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return "http://localhost:7900/vnc.html?autoconnect=1&resize=scale"
        return value

    @property
    def database_ssl(self) -> bool:
        return _host_needs_ssl(self.database_url)

    @property
    def use_memory_redis(self) -> bool:
        raw = (self.redis_url or "").strip().lower()
        return raw in {"", "memory", "memory://", "none", "off"}


settings = Settings()


def cors_origin_list() -> list[str]:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]
