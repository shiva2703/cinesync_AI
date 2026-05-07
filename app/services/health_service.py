from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from time import monotonic

import aiofiles

from app.config.settings import Settings
from app.schemas.health import HealthComponent, HealthResponse
from app.services.ffmpeg_service import FFmpegService
from app.storage.local import LocalStorage


class HealthService:
    """Compute health status for internal dependencies."""

    def __init__(
        self,
        settings: Settings,
        storage: LocalStorage,
        ffmpeg_service: FFmpegService,
        started_at: float,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.ffmpeg_service = ffmpeg_service
        self.started_at = started_at

    async def get_health(self) -> HealthResponse:
        ffmpeg_available = await self.ffmpeg_service.is_available()
        ffmpeg_version = await self.ffmpeg_service.get_version() if ffmpeg_available else None
        disk_usage = shutil.disk_usage(self.settings.storage_path)
        temp_ok = await self._temp_storage_writable()

        overall_status = "ok" if ffmpeg_available and temp_ok else "degraded"
        return HealthResponse(
            status=overall_status,
            uptime_seconds=round(monotonic() - self.started_at, 3),
            ffmpeg=HealthComponent(
                status="ok" if ffmpeg_available else "unavailable",
                details={"available": ffmpeg_available, "version": ffmpeg_version or "missing"},
            ),
            disk=HealthComponent(
                status="ok",
                details={
                    "total_bytes": int(disk_usage.total),
                    "used_bytes": int(disk_usage.used),
                    "free_bytes": int(disk_usage.free),
                },
            ),
            temp_storage=HealthComponent(
                status="ok" if temp_ok else "error",
                details={"path": str(self.settings.temp_path), "writable": temp_ok},
            ),
        )

    async def _temp_storage_writable(self) -> bool:
        probe_file = self.settings.temp_path / ".healthcheck"
        try:
            async with aiofiles.open(probe_file, "w", encoding="utf-8") as file_handle:
                await file_handle.write("ok")
            await asyncio.to_thread(probe_file.unlink, True)
            return True
        except OSError:
            return False
