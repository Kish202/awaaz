"""Runtime configuration for the API and worker, read from environment / `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://awaaz:awaaz@localhost:5432/awaaz",
        description="SQLAlchemy URL. Use the psycopg (v3) driver.",
    )
    redis_url: str = Field(default="redis://127.0.0.1:6379/0", description="Celery broker + result backend")

    # Audio storage. "local" for development; "cloudinary" in production.
    storage_backend: Literal["local", "cloudinary"] = "local"
    storage_dir: Path = Field(default=Path("data/recordings"), description="Local backend: where files live")
    cloudinary_url: str | None = Field(
        default=None, description="cloudinary://<api_key>:<api_secret>@<cloud_name> (from the Cloudinary console)"
    )
    cloudinary_folder: str = Field(default="awaaz", description="Top-level folder for all assets")

    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"])
    admin_token: str | None = Field(default=None, description="Bearer token for moderation endpoints")

    # Recording acceptance rules applied by the worker.
    min_clip_seconds: float = 1.0
    max_clip_seconds: float = 15.0
    silence_rms_threshold: float = 0.004  # fraction of full scale; below this the clip is treated as silent
    target_sample_rate: int = 16000

    # Validation: how many agreeing votes settle a recording.
    votes_to_settle: int = 2

    # Upload abuse limits.
    recording_rate_limit: str = "30/minute"
    max_upload_bytes: int = 10 * 1024 * 1024

    host: str = "127.0.0.1"
    port: int = 8000


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
