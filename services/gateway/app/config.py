from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
