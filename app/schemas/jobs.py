from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.models.domain import JobStatus, TimelineItem


class CreateJobRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    upload_ids: list[str] = Field(min_length=1)
    audio_upload_id: str | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: float
    stage: str
    error: str | None = None
    updated_at: datetime


class JobDetailResponse(JobStatusResponse):
    prompt: str
    upload_ids: list[str]
    audio_upload_id: str | None = None
    timeline: list[TimelineItem]
    output_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus
    stage: str


class JobOutputResponse(BaseModel):
    job_id: str
    output_path: str
    timeline_path: str | None = None
    metadata_path: str | None = None
