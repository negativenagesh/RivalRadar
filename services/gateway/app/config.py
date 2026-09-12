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


settings = Settings()
