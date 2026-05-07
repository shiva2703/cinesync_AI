from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SuccessResponse(BaseModel):
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
