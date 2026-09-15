from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_database_url(url: str) -> str:
    """Render/Neon often hand postgres:// — SQLAlchemy async needs postgresql+asyncpg://."""
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rivalradar:rivalradar@localhost:5432/rivalradar"
    redis_url: str = "redis://localhost:6379/0"
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


settings = Settings()


def cors_origin_list() -> list[str]:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]
