from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from app.config.settings import Settings
from app.logging.setup import configure_logging
from app.pipeline.orchestrator import PipelineOrchestrator
from app.repositories.job_repository import InMemoryJobRepository
from app.services.ai_service import MultimodalAIService
from app.services.audio_analysis_service import AudioAnalysisService
from app.services.ffmpeg_service import FFmpegService
from app.services.health_service import HealthService
from app.services.render_service import RenderService
from app.services.timeline_service import TimelineService
from app.services.video_analysis_service import VideoAnalysisService
from app.storage.local import LocalStorage
from app.workers.job_manager import InMemoryJobManager


@dataclass(slots=True)
class ApplicationContainer:
    """Wires all application dependencies together."""

    settings: Settings
    storage: LocalStorage
    ffmpeg_service: FFmpegService
    video_analysis_service: VideoAnalysisService
    audio_analysis_service: AudioAnalysisService
    ai_service: MultimodalAIService
    timeline_service: TimelineService
    render_service: RenderService
    pipeline_orchestrator: PipelineOrchestrator
    job_repository: InMemoryJobRepository
    job_manager: InMemoryJobManager
    health_service: HealthService
    started_at: float

    @classmethod
    async def build(cls, settings: Settings) -> "ApplicationContainer":
        configure_logging(settings)
        storage = LocalStorage(settings=settings)
        await storage.initialize()

        ffmpeg_service = FFmpegService(settings=settings)
        video_analysis_service = VideoAnalysisService(settings=settings, storage=storage)
        audio_analysis_service = AudioAnalysisService(settings=settings)
        ai_service = MultimodalAIService(settings=settings)
        timeline_service = TimelineService()
        render_service = RenderService(
            settings=settings,
            storage=storage,
            ffmpeg_service=ffmpeg_service,
        )
        job_repository = InMemoryJobRepository()
        pipeline_orchestrator = PipelineOrchestrator(
            settings=settings,
            storage=storage,
            ffmpeg_service=ffmpeg_service,
            video_analysis_service=video_analysis_service,
            audio_analysis_service=audio_analysis_service,
            ai_service=ai_service,
            timeline_service=timeline_service,
            render_service=render_service,
            job_repository=job_repository,
        )
        job_manager = InMemoryJobManager(
            settings=settings,
            repository=job_repository,
            pipeline_orchestrator=pipeline_orchestrator,
        )
        health_service = HealthService(
            settings=settings,
            storage=storage,
            ffmpeg_service=ffmpeg_service,
            started_at=monotonic(),
        )

        return cls(
            settings=settings,
            storage=storage,
            ffmpeg_service=ffmpeg_service,
            video_analysis_service=video_analysis_service,
            audio_analysis_service=audio_analysis_service,
            ai_service=ai_service,
            timeline_service=timeline_service,
            render_service=render_service,
            pipeline_orchestrator=pipeline_orchestrator,
            job_repository=job_repository,
            job_manager=job_manager,
            health_service=health_service,
            started_at=monotonic(),
        )

    async def shutdown(self) -> None:
        await self.job_manager.shutdown()
