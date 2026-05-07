from __future__ import annotations

import asyncio
from pathlib import Path

import librosa
import numpy as np
import structlog

from app.config.settings import Settings
from app.models.domain import AudioAnalysis, TimelineItem, UploadAsset


class AudioAnalysisService:
    """Analyze audio tracks and align timeline cuts to beats."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

    async def analyze_audio(self, asset: UploadAsset) -> AudioAnalysis:
        self.logger.info("audio_analysis_started", upload_id=asset.upload_id)
        analysis = await asyncio.to_thread(self._analyze_audio_sync, asset.stored_path)
        self.logger.info(
            "audio_analysis_completed",
            upload_id=asset.upload_id,
            tempo=analysis.tempo,
            duration=analysis.duration,
        )
        return analysis

    def align_timeline(self, timeline: list[TimelineItem], analysis: AudioAnalysis | None) -> list[TimelineItem]:
        if not analysis or not analysis.beat_times:
            return timeline

        aligned: list[TimelineItem] = []
        for index, item in enumerate(timeline):
            target_start = 0.0 if index == 0 else aligned[-1].end
            target_end = max(item.end, target_start + 0.5)
            snapped_end = self._nearest_beat(target_end, analysis.beat_times)
            if snapped_end <= target_start:
                snapped_end = target_end
            aligned.append(item.model_copy(update={"start": target_start, "end": snapped_end}, deep=True))
        return aligned

    def _analyze_audio_sync(self, audio_path: Path) -> AudioAnalysis:
        signal, sample_rate = librosa.load(audio_path, sr=None, mono=True)
        tempo, beat_frames = librosa.beat.beat_track(y=signal, sr=sample_rate)
        beat_times = librosa.frames_to_time(beat_frames, sr=sample_rate).tolist()
        duration = float(librosa.get_duration(y=signal, sr=sample_rate))
        rms_energy = float(np.mean(librosa.feature.rms(y=signal)))
        return AudioAnalysis(
            tempo=round(float(tempo), 2),
            beat_times=[round(float(beat), 3) for beat in beat_times],
            duration=round(duration, 3),
            rms_energy=round(rms_energy, 6),
        )

    def _nearest_beat(self, target_time: float, beat_times: list[float]) -> float:
        return min(beat_times, key=lambda beat_time: abs(beat_time - target_time))
