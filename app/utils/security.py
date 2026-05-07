from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from fastapi import UploadFile

from app.config.settings import Settings
from app.core.exceptions import ValidationError

SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    name = SAFE_FILENAME_PATTERN.sub("_", name)
    if not name or name.startswith("."):
        raise ValidationError("Invalid filename", error_code="invalid_filename")
    return name


def validate_upload(upload_file: UploadFile, settings: Settings) -> str:
    filename = sanitize_filename(upload_file.filename or "upload.bin")
    extension = Path(filename).suffix.lower()
    mime_type = (upload_file.content_type or mimetypes.guess_type(filename)[0] or "").lower()

    if extension not in settings.allowed_extensions:
        raise ValidationError(
            message=f"Unsupported file extension '{extension}'",
            error_code="unsupported_extension",
            details={"allowed_extensions": settings.allowed_extensions},
        )

    if mime_type and mime_type not in settings.allowed_mime_types:
        raise ValidationError(
            message=f"Unsupported mime type '{mime_type}'",
            error_code="unsupported_mime_type",
            details={"allowed_mime_types": settings.allowed_mime_types},
        )

    return filename
