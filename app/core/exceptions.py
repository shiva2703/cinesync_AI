from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    """Base application exception with structured metadata."""

    message: str
    error_code: str
    status_code: int = 500
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message


class ValidationError(AppError):
    def __init__(self, message: str, error_code: str = "validation_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=400,
            details=details or {},
        )


class StorageError(AppError):
    def __init__(self, message: str, error_code: str = "storage_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details or {},
        )


class FFmpegExecutionError(AppError):
    def __init__(self, message: str, error_code: str = "ffmpeg_execution_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=502,
            details=details or {},
        )


class AIInferenceError(AppError):
    def __init__(self, message: str, error_code: str = "ai_inference_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=502,
            details=details or {},
        )


class PipelineExecutionError(AppError):
    def __init__(self, message: str, error_code: str = "pipeline_execution_error", details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            error_code=error_code,
            status_code=500,
            details=details or {},
        )
