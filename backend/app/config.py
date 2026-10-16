"""Runtime configuration, read from environment variables (12-factor style)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "carequeue"
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    git_sha: str = Field(default="local", alias="GIT_SHA")

    # SQLite by default so `uvicorn app.main:app` works on a laptop without
    # Postgres. Compose and Helm always set a postgresql+psycopg:// URL.
    database_url: str = Field(default="sqlite:///./carequeue-dev.db", alias="DATABASE_URL")

    # Comma separated list, e.g. "http://localhost:3000,http://localhost:5173"
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # The clinic's local timezone decides what "today" and "a past slot" mean.
    clinic_timezone: str = Field(default="Asia/Kolkata", alias="CLINIC_TIMEZONE")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
