from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.domain import AssetType


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    asset_type: AssetType
    mime_type: str
    size_bytes: int
    created_at: datetime


class UploadListResponse(BaseModel):
    uploads: list[UploadResponse]
