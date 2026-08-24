from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    environment: str = "development"

    database_url: str
    redis_url: str

    openai_api_key: str | None = None

    github_app_id: str
    github_client_id: str
    github_client_secret: str
    github_private_key_path: str
    github_redirect_uri: str

    session_secret: str
    token_encryption_key: str


    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()