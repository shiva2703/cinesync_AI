from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AssetType(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"


class UploadAsset(BaseModel):
    upload_id: str
    filename: str
    stored_path: Path
    public_name: str
    size_bytes: int
    mime_type: str
    extension: str
    asset_type: AssetType
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClipAnalysis(BaseModel):
    clip_id: str
    asset_type: AssetType
    source_path: Path
    motion_score: float
    brightness: float
    duration: float
    fps: float
    width: int
    height: int
    sampled_frames: list[Path] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptContext(BaseModel):
    raw_prompt: str
    keywords: list[str]
    pacing: str
    tone: str
    target_duration: float
    overlay_texts: list[str] = Field(default_factory=list)


class TimelineItem(BaseModel):
    clip_id: str
    start: float
    end: float
    transition: str = "cut"
    overlay_text: str = ""
    score: float = 0.0


class AudioAnalysis(BaseModel):
    tempo: float
    beat_times: list[float]
    duration: float
    rms_energy: float


class RenderArtifact(BaseModel):
    output_path: Path
    preview_path: Path | None = None
    timeline_path: Path
    metadata_path: Path
    duration: float
    resolution: str


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    prompt: str
    upload_ids: list[str]
    audio_upload_id: str | None = None
    progress: float = 0.0
    stage: str = "queued"
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    timeline: list[TimelineItem] = Field(default_factory=list)
    output_path: Path | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
