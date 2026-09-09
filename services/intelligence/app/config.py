from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rivalradar:rivalradar@localhost:5432/rivalradar"
    ingestion_service_url: str = "http://localhost:8001"


settings = Settings()
