from __future__ import annotations

from pathlib import Path

import structlog

from app.config.settings import Settings
from app.core.exceptions import PipelineExecutionError
from app.models.domain import AssetType
from app.repositories.job_repository import InMemoryJobRepository
from app.services.ai_service import MultimodalAIService
from app.services.audio_analysis_service import AudioAnalysisService
from app.services.ffmpeg_service import FFmpegService
from app.services.render_service import RenderService
from app.services.timeline_service import TimelineService
from app.services.video_analysis_service import VideoAnalysisService
from app.storage.local import LocalStorage


class PipelineOrchestrator:
    """End-to-end media orchestration for CineSync AI jobs."""

    def __init__(
        self,
        settings: Settings,
        storage: LocalStorage,
        ffmpeg_service: FFmpegService,
        video_analysis_service: VideoAnalysisService,
        audio_analysis_service: AudioAnalysisService,
        ai_service: MultimodalAIService,
        timeline_service: TimelineService,
        render_service: RenderService,
        job_repository: InMemoryJobRepository,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.ffmpeg_service = ffmpeg_service
        self.video_analysis_service = video_analysis_service
        self.audio_analysis_service = audio_analysis_service
        self.ai_service = ai_service
        self.timeline_service = timeline_service
        self.render_service = render_service
        self.job_repository = job_repository
        self.logger = structlog.get_logger(__name__)

    async def run(self, job_id: str) -> None:
        job = await self.job_repository.get(job_id)
        await self.job_repository.update(job_id, stage="ingestion", progress=0.05)
        workspace = await self.storage.create_job_workspace(job_id)

        visual_assets = await self.storage.stage_uploads_for_job(job_id, job.upload_ids)
        audio_asset = None
        if job.audio_upload_id:
            audio_asset = (await self.storage.stage_uploads_for_job(job_id, [job.audio_upload_id]))[0]

        await self.job_repository.update(job_id, stage="video_analysis", progress=0.2)
        visual_analyses = []
        for asset in visual_assets:
            if asset.asset_type == AssetType.AUDIO:
                continue
            analysis = await self.video_analysis_service.analyze_asset(asset, workspace["temp"])
            ffprobe_metadata = {}
            if asset.asset_type == AssetType.VIDEO and await self.ffmpeg_service.is_available():
                ffprobe_metadata = await self.ffmpeg_service.extract_metadata(asset.stored_path)
            visual_analyses.append(
                analysis.model_copy(update={"metadata": {**analysis.metadata, "ffprobe": ffprobe_metadata}}, deep=True)
            )

        await self.job_repository.update(job_id, stage="audio_analysis", progress=0.4)
        audio_analysis = await self.audio_analysis_service.analyze_audio(audio_asset) if audio_asset else None

        await self.job_repository.update(job_id, stage="cognitive_layer", progress=0.55)
        prompt_context = await self.ai_service.interpret_prompt(job.prompt, visual_analyses)
        semantic_scores = await self.ai_service.semantic_scores(prompt_context, visual_analyses)

        await self.job_repository.update(job_id, stage="timeline_compiler", progress=0.7)
        timeline = self.timeline_service.build_timeline(prompt_context, visual_analyses, semantic_scores)
        timeline = self.audio_analysis_service.align_timeline(timeline, audio_analysis)
        await self.storage.write_json(
            self.storage.get_job_timeline_file(job_id),
            [item.model_dump(mode="json") for item in timeline],
        )
        await self.job_repository.update(job_id, timeline=timeline)

        await self.job_repository.update(job_id, stage="rendering", progress=0.85)
        artifact = await self.render_service.render(job_id, timeline, visual_analyses, audio_asset)

        job_metadata = {
            "job_id": job_id,
            "prompt_context": prompt_context.model_dump(mode="json"),
            "audio_analysis": audio_analysis.model_dump(mode="json") if audio_analysis else None,
            "clip_analyses": [analysis.model_dump(mode="json") for analysis in visual_analyses],
            "artifact": artifact.model_dump(mode="json"),
        }
        await self.storage.write_json(self.storage.get_job_metadata_file(job_id), job_metadata)
        await self.storage.cleanup_job_temp(job_id)

        await self.job_repository.update(
            job_id,
            stage="completed",
            progress=1.0,
            output_path=artifact.output_path,
            metadata={
                "timeline_path": str(artifact.timeline_path),
                "metadata_path": str(artifact.metadata_path),
                "preview_path": str(artifact.preview_path) if artifact.preview_path else None,
                "duration": artifact.duration,
                "resolution": artifact.resolution,
            },
        )
        self.logger.info("pipeline_completed", job_id=job_id, output_path=str(artifact.output_path))

    async def fail_job(self, job_id: str, exc: Exception) -> None:
        message = str(exc)
        if not isinstance(exc, PipelineExecutionError):
            exc = PipelineExecutionError(message=message or "Pipeline execution failed")
        await self.job_repository.update(job_id, stage="failed", error=message, progress=1.0)
