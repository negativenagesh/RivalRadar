from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rivalradar:rivalradar@localhost:5432/rivalradar"
    redis_url: str = "redis://localhost:6379/0"
    object_store_root: str = "/data/objects"
    browser_headless: bool = True
    youtube_api_key: str | None = None


settings = Settings()
