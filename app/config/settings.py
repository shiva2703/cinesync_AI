from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="CineSync AI", alias="APP_NAME")
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        alias="APP_ENV",
    )
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: list[str] = Field(default=["*"], alias="CORS_ORIGINS")

    storage_path: Path = Field(default=Path("storage"), alias="STORAGE_PATH")
    temp_path: Path = Field(default=Path("storage/shared/temp"), alias="TEMP_PATH")
    output_path: Path = Field(default=Path("storage/shared/outputs"), alias="OUTPUT_PATH")
    logs_path: Path = Field(default=Path("logs"), alias="LOGS_PATH")
    ffmpeg_binary: str = Field(default="ffmpeg", alias="FFMPEG_BINARY")
    ffprobe_binary: str = Field(default="ffprobe", alias="FFPROBE_BINARY")
    max_upload_size: int = Field(default=268_435_456, alias="MAX_UPLOAD_SIZE")
    model_cache_dir: Path = Field(default=Path("models-cache"), alias="MODEL_CACHE_DIR")
    cleanup_enabled: bool = Field(default=True, alias="CLEANUP_ENABLED")
    temp_file_ttl_seconds: int = Field(default=3600, alias="TEMP_FILE_TTL_SECONDS")
    job_timeout_seconds: int = Field(default=1800, alias="JOB_TIMEOUT_SECONDS")
    ffmpeg_timeout_seconds: int = Field(default=600, alias="FFMPEG_TIMEOUT_SECONDS")
    ffmpeg_retry_attempts: int = Field(default=2, alias="FFMPEG_RETRY_ATTEMPTS")
    allowed_extensions: list[str] = Field(
        default=[".mp4", ".mov", ".mkv", ".avi", ".png", ".jpg", ".jpeg", ".wav", ".mp3"],
        alias="ALLOWED_EXTENSIONS",
    )
    allowed_mime_types: list[str] = Field(
        default=[
            "video/mp4",
            "video/quicktime",
            "video/x-matroska",
            "video/x-msvideo",
            "image/png",
            "image/jpeg",
            "audio/wav",
            "audio/mpeg",
            "audio/x-wav",
        ],
        alias="ALLOWED_MIME_TYPES",
    )

    ai_server_url: HttpUrl | None = Field(default=None, alias="AI_SERVER_URL")
    media_server_url: HttpUrl | None = Field(default=None, alias="MEDIA_SERVER_URL")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    r2_account_id: str | None = Field(default=None, alias="R2_ACCOUNT_ID")
    r2_access_key_id: str | None = Field(default=None, alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str | None = Field(default=None, alias="R2_SECRET_ACCESS_KEY")
    r2_bucket_name: str | None = Field(default=None, alias="R2_BUCKET_NAME")
    r2_endpoint_url: HttpUrl | None = Field(default=None, alias="R2_ENDPOINT_URL")

    embedding_model_name: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL_NAME",
    )
    classifier_model_name: str = Field(
        default="distilbert-base-uncased-finetuned-sst-2-english",
        alias="CLASSIFIER_MODEL_NAME",
    )
    enable_local_ai_fallback: bool = Field(default=True, alias="ENABLE_LOCAL_AI_FALLBACK")

    @field_validator("storage_path", "temp_path", "output_path", "logs_path", "model_cache_dir")
    @classmethod
    def normalize_path(cls, value: Path) -> Path:
        return value.expanduser()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return normalized

    @field_validator("max_upload_size")
    @classmethod
    def validate_max_upload_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("MAX_UPLOAD_SIZE must be greater than zero")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return parts or ["*"]
        return value

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_allowed_extensions(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return [part.lower() for part in value]

    @field_validator("allowed_mime_types", mode="before")
    @classmethod
    def parse_allowed_mime_types(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return [part.lower() for part in value]

    @field_validator("ai_server_url", "media_server_url", "r2_endpoint_url", mode="before")
    @classmethod
    def blank_urls_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
