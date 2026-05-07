from __future__ import annotations

from pydantic import BaseModel


class HealthComponent(BaseModel):
    status: str
    details: dict[str, str | int | float | bool]


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    ffmpeg: HealthComponent
    disk: HealthComponent
    temp_storage: HealthComponent
