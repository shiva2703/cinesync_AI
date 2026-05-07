from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import numpy as np
import structlog

from app.config.settings import Settings
from app.models.domain import AssetType, ClipAnalysis, RenderArtifact, TimelineItem, UploadAsset
from app.services.ffmpeg_service import FFmpegService
from app.storage.local import LocalStorage


class RenderService:
    """Compose output videos with OpenCV and optimize with FFmpeg when available."""

    def __init__(self, settings: Settings, storage: LocalStorage, ffmpeg_service: FFmpegService) -> None:
        self.settings = settings
        self.storage = storage
        self.ffmpeg_service = ffmpeg_service
        self.logger = structlog.get_logger(__name__)

    async def render(
        self,
        job_id: str,
        timeline: list[TimelineItem],
        clip_analyses: list[ClipAnalysis],
        audio_asset: UploadAsset | None,
    ) -> RenderArtifact:
        outputs_dir = self.storage.get_job_output_file(job_id).parent
        outputs_dir.mkdir(parents=True, exist_ok=True)
        raw_output = outputs_dir / "render_raw.mp4"
        final_output = outputs_dir / "final.mp4"
        preview_path = outputs_dir / "preview.jpg"
        timeline_path = self.storage.get_job_timeline_file(job_id)
        metadata_path = self.storage.get_job_metadata_file(job_id)

        clip_lookup = {analysis.clip_id: analysis for analysis in clip_analyses}
        self.logger.info("render_started", job_id=job_id, clip_count=len(clip_analyses))
        duration = await asyncio.to_thread(
            self._compose_with_opencv,
            raw_output,
            preview_path,
            timeline,
            clip_lookup,
        )

        if await self.ffmpeg_service.is_available():
            optimized_path = outputs_dir / "render_vertical.mp4"
            await self.ffmpeg_service.resize_for_vertical(raw_output, optimized_path)
            if audio_asset:
                await self.ffmpeg_service.mux_audio(optimized_path, audio_asset.stored_path, final_output, duration)
            else:
                await asyncio.to_thread(optimized_path.replace, final_output)
        else:
            final_output = raw_output

        self.logger.info("render_completed", job_id=job_id, output_path=str(final_output))
        return RenderArtifact(
            output_path=final_output,
            preview_path=preview_path if preview_path.exists() else None,
            timeline_path=timeline_path,
            metadata_path=metadata_path,
            duration=round(duration, 3),
            resolution="1080x1920",
        )

    def _compose_with_opencv(
        self,
        output_path: Path,
        preview_path: Path,
        timeline: list[TimelineItem],
        clip_lookup: dict[str, ClipAnalysis],
    ) -> float:
        fps = 24
        width = 1080
        height = 1920
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
        if not writer.isOpened():
            raise RuntimeError(f"Unable to open video writer for {output_path}")
        previous_frame: np.ndarray | None = None
        preview_written = False
        total_duration = 0.0

        for index, item in enumerate(timeline):
            analysis = clip_lookup[item.clip_id]
            next_analysis = clip_lookup[timeline[index + 1].clip_id] if index + 1 < len(timeline) else None
            segment_frames = self._segment_frames(analysis, item, fps, width, height)
            for frame in segment_frames:
                writer.write(frame)
                if not preview_written:
                    cv2.imwrite(str(preview_path), frame)
                    preview_written = True
                previous_frame = frame
            total_duration += max(item.end - item.start, 0.0)

            if item.transition == "fade" and previous_frame is not None and next_analysis is not None:
                next_frame = self._first_frame(next_analysis, width, height)
                for alpha in np.linspace(0.0, 1.0, num=max(int(fps * 0.4), 1)):
                    blended = cv2.addWeighted(previous_frame, 1.0 - alpha, next_frame, alpha, 0)
                    writer.write(blended)
                    total_duration += 1 / fps

        writer.release()
        return total_duration

    def _segment_frames(
        self,
        analysis: ClipAnalysis,
        item: TimelineItem,
        fps: int,
        width: int,
        height: int,
    ) -> list[np.ndarray]:
        if analysis.asset_type == AssetType.IMAGE:
            frame = self._read_image_frame(analysis.source_path, width, height)
            return [self._draw_overlay(frame.copy(), item.overlay_text) for _ in range(max(int((item.end - item.start) * fps), 1))]

        capture = cv2.VideoCapture(str(analysis.source_path))
        source_fps = analysis.fps or fps
        capture.set(cv2.CAP_PROP_POS_MSEC, item.start * 1000)
        expected_frames = max(int((item.end - item.start) * fps), 1)
        frames: list[np.ndarray] = []

        while len(frames) < expected_frames:
            success, frame = capture.read()
            if not success:
                break
            fitted = self._fit_frame(frame, width, height)
            frames.append(self._draw_overlay(fitted, item.overlay_text))
            skip = max(int(round(source_fps / fps)) - 1, 0)
            for _ in range(skip):
                capture.read()

        capture.release()
        if not frames:
            fallback = np.zeros((height, width, 3), dtype=np.uint8)
            frames = [self._draw_overlay(fallback, item.overlay_text) for _ in range(expected_frames)]
        return frames

    def _first_frame(self, analysis: ClipAnalysis, width: int, height: int) -> np.ndarray:
        if analysis.asset_type == AssetType.IMAGE:
            return self._read_image_frame(analysis.source_path, width, height)
        capture = cv2.VideoCapture(str(analysis.source_path))
        success, frame = capture.read()
        capture.release()
        if not success:
            return np.zeros((height, width, 3), dtype=np.uint8)
        return self._fit_frame(frame, width, height)

    def _read_image_frame(self, path: Path, width: int, height: int) -> np.ndarray:
        frame = cv2.imread(str(path))
        if frame is None:
            return np.zeros((height, width, 3), dtype=np.uint8)
        return self._fit_frame(frame, width, height)

    def _fit_frame(self, frame: np.ndarray, width: int, height: int) -> np.ndarray:
        source_height, source_width = frame.shape[:2]
        scale = min(width / source_width, height / source_height)
        resized = cv2.resize(frame, (int(source_width * scale), int(source_height * scale)))
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        x_offset = (width - resized.shape[1]) // 2
        y_offset = (height - resized.shape[0]) // 2
        canvas[y_offset : y_offset + resized.shape[0], x_offset : x_offset + resized.shape[1]] = resized
        return canvas

    def _draw_overlay(self, frame: np.ndarray, text: str) -> np.ndarray:
        if not text:
            return frame
        cv2.rectangle(frame, (60, 1680), (1020, 1820), (0, 0, 0), thickness=-1)
        cv2.putText(
            frame,
            text[:50],
            (90, 1760),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.3,
            (255, 255, 255),
            3,
            cv2.LINE_AA,
        )
        return frame
