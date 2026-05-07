from __future__ import annotations

import math
from pathlib import Path

import asyncio
import cv2
import numpy as np
import structlog

from app.config.settings import Settings
from app.models.domain import AssetType, ClipAnalysis, UploadAsset
from app.storage.local import LocalStorage


class VideoAnalysisService:
    """Analyze video and image assets using OpenCV."""

    def __init__(self, settings: Settings, storage: LocalStorage) -> None:
        self.settings = settings
        self.storage = storage
        self.logger = structlog.get_logger(__name__)

    async def analyze_asset(self, asset: UploadAsset, temp_dir: Path) -> ClipAnalysis:
        self.logger.info("video_analysis_started", upload_id=asset.upload_id, asset_type=asset.asset_type.value)
        analysis = await asyncio.to_thread(self._analyze_asset_sync, asset, temp_dir)
        self.logger.info(
            "video_analysis_completed",
            upload_id=asset.upload_id,
            motion_score=analysis.motion_score,
            brightness=analysis.brightness,
            duration=analysis.duration,
        )
        return analysis

    def _analyze_asset_sync(self, asset: UploadAsset, temp_dir: Path) -> ClipAnalysis:
        temp_dir.mkdir(parents=True, exist_ok=True)

        if asset.asset_type == AssetType.IMAGE:
            image = cv2.imread(str(asset.stored_path))
            if image is None:
                raise ValueError(f"Unable to read image {asset.stored_path}")
            brightness = float(np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)))
            height, width = image.shape[:2]
            keyframe_path = temp_dir / f"{asset.upload_id}_frame_0.jpg"
            cv2.imwrite(str(keyframe_path), image)
            return ClipAnalysis(
                clip_id=asset.upload_id,
                asset_type=asset.asset_type,
                source_path=asset.stored_path,
                motion_score=0.0,
                brightness=round(brightness, 2),
                duration=3.0,
                fps=0.0,
                width=width,
                height=height,
                sampled_frames=[keyframe_path],
                metadata={"type": "image"},
            )

        capture = cv2.VideoCapture(str(asset.stored_path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration = round(frame_count / fps, 3) if fps > 0 else 0.0
        sample_interval = max(int(math.floor(fps)), 1)

        frame_index = 0
        sampled_frames: list[Path] = []
        grayscale_frames: list[np.ndarray] = []

        while True:
            success, frame = capture.read()
            if not success:
                break
            if frame_index % sample_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                grayscale_frames.append(gray)
                keyframe_path = temp_dir / f"{asset.upload_id}_frame_{len(sampled_frames)}.jpg"
                cv2.imwrite(str(keyframe_path), frame)
                sampled_frames.append(keyframe_path)
            frame_index += 1

        capture.release()

        if not grayscale_frames:
            grayscale_frames.append(np.zeros((32, 32), dtype=np.uint8))

        brightness = float(np.mean([np.mean(frame) for frame in grayscale_frames]))
        diffs: list[float] = []
        for previous, current in zip(grayscale_frames, grayscale_frames[1:]):
            diffs.append(float(np.mean(cv2.absdiff(previous, current)) / 255.0))
        motion_score = round(float(np.mean(diffs)) if diffs else 0.0, 4)

        return ClipAnalysis(
            clip_id=asset.upload_id,
            asset_type=asset.asset_type,
            source_path=asset.stored_path,
            motion_score=motion_score,
            brightness=round(brightness, 2),
            duration=duration,
            fps=round(fps, 2),
            width=width,
            height=height,
            sampled_frames=sampled_frames,
            metadata={"frame_count": frame_count},
        )
