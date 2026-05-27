"""Application settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "Agent-First Transcription API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-me"
    ADMIN_BOOTSTRAP_SECRET: str = "local-dev-bootstrap"
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/transcription_db"

    GCP_PROJECT_ID: str = ""
    GCP_LOCATION: str = "us-central1"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    UPLOAD_DIR: str = "data/uploads"
    CACHE_DIR: str = "data/cache"
    MAX_UPLOAD_BYTES: int = 100 * 1024 * 1024  # 100MB

    DEFAULT_MONTHLY_JOB_QUOTA: int = 500
    DEFAULT_RATE_LIMIT_RPM: int = 30
    GLOBAL_RATE_LIMIT_RPM: int = 120

    # Estimated billable units per job for quota accounting
    COST_PER_JOB_USD: float = 0.05

    WORKER_POOL_SIZE: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
