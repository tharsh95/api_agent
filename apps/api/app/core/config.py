from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    environment: str = "development"

    database_url: str
    redis_url: str

    openai_api_key: str | None = None

    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_redirect_uri: str | None = None

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()