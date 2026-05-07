from __future__ import annotations

from itertools import cycle

from app.core.exceptions import ValidationError
from app.models.domain import ClipAnalysis, PromptContext, TimelineItem


class TimelineService:
    """Deterministically rank clips and compile an edit decision list."""

    def build_timeline(
        self,
        prompt_context: PromptContext,
        clip_analyses: list[ClipAnalysis],
        semantic_scores: dict[str, float],
    ) -> list[TimelineItem]:
        if not clip_analyses:
            raise ValidationError("At least one visual asset is required to build a timeline")

        ranked = sorted(
            clip_analyses,
            key=lambda analysis: (
                -semantic_scores.get(analysis.clip_id, 0.0),
                -analysis.motion_score,
                analysis.clip_id,
            ),
        )

        overlay_cycle = cycle(prompt_context.overlay_texts or [""])
        transition = "fade" if prompt_context.pacing == "slow" else "cut"
        timeline: list[TimelineItem] = []
        remaining_duration = prompt_context.target_duration
        clip_offsets: dict[str, float] = {}
        minimum_duration = {"fast": 1.5, "balanced": 2.5, "slow": 4.0}[prompt_context.pacing]
        maximum_duration = {"fast": 3.0, "balanced": 4.5, "slow": 6.0}[prompt_context.pacing]

        rank_index = 0
        while remaining_duration > 0.25:
            analysis = ranked[rank_index % len(ranked)]
            clip_duration = analysis.duration if analysis.duration > 0 else minimum_duration
            allocated = min(maximum_duration, max(minimum_duration, clip_duration))
            allocated = min(allocated, remaining_duration)
            start = clip_offsets.get(analysis.clip_id, 0.0)
            if analysis.duration > 0 and start >= analysis.duration:
                start = 0.0
            end = min(start + allocated, clip_duration) if analysis.duration > 0 else allocated
            if analysis.duration > 0 and end <= start:
                start = 0.0
                end = min(allocated, clip_duration)
            score = semantic_scores.get(analysis.clip_id, 0.0)
            timeline.append(
                TimelineItem(
                    clip_id=analysis.clip_id,
                    start=round(start, 3),
                    end=round(end, 3),
                    transition=transition if timeline else "cut",
                    overlay_text=next(overlay_cycle),
                    score=round(score, 4),
                )
            )
            clip_offsets[analysis.clip_id] = round(end, 3)
            remaining_duration = round(remaining_duration - allocated, 3)
            rank_index += 1
            if rank_index >= len(ranked) and remaining_duration < minimum_duration:
                break

        return timeline
