from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.core.exceptions import ValidationError


def validate_environment(settings: Settings) -> None:
    """Validate environment configuration before the app starts."""

    _validate_paths(
        [
            settings.storage_path,
            settings.temp_path,
            settings.output_path,
            settings.logs_path,
            settings.model_cache_dir,
        ]
    )

    if settings.ffmpeg_retry_attempts < 1:
        raise ValidationError(
            message="FFMPEG_RETRY_ATTEMPTS must be at least 1",
            error_code="invalid_ffmpeg_retry_attempts",
        )

    if settings.job_timeout_seconds < 60:
        raise ValidationError(
            message="JOB_TIMEOUT_SECONDS must be at least 60",
            error_code="invalid_job_timeout",
        )


def _validate_paths(paths: list[Path]) -> None:
    for path in paths:
        if ".." in path.as_posix().split("/"):
            raise ValidationError(
                message=f"Path '{path}' must not contain parent traversal segments",
                error_code="invalid_path",
            )
