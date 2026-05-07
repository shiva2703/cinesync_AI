from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np
import structlog

from app.config.settings import Settings
from app.core.exceptions import AIInferenceError
from app.models.domain import ClipAnalysis, PromptContext

STOP_WORDS = {
    "a",
    "an",
    "and",
    "the",
    "for",
    "to",
    "of",
    "with",
    "on",
    "in",
    "at",
    "from",
    "into",
    "create",
    "make",
    "video",
    "clip",
    "clips",
}


class MultimodalAIService:
    """Prompt interpretation with deterministic fallbacks and optional local models."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

    async def interpret_prompt(self, prompt: str, clip_analyses: list[ClipAnalysis]) -> PromptContext:
        self.logger.info("ai_inference_started", operation="interpret_prompt")
        keywords = [token for token in _tokenize(prompt) if token not in STOP_WORDS]
        pacing = _infer_pacing(keywords)
        tone = await self._infer_tone(prompt)
        target_duration = _infer_target_duration(prompt, clip_analyses, pacing)
        overlay_texts = _build_overlay_texts(prompt, keywords)
        context = PromptContext(
            raw_prompt=prompt,
            keywords=keywords[:12],
            pacing=pacing,
            tone=tone,
            target_duration=target_duration,
            overlay_texts=overlay_texts,
        )
        self.logger.info(
            "ai_inference_completed",
            operation="interpret_prompt",
            pacing=context.pacing,
            tone=context.tone,
            target_duration=context.target_duration,
        )
        return context

    async def semantic_scores(
        self,
        prompt_context: PromptContext,
        clip_analyses: list[ClipAnalysis],
    ) -> dict[str, float]:
        if not clip_analyses:
            return {}

        scores = {analysis.clip_id: self._heuristic_similarity(prompt_context, analysis) for analysis in clip_analyses}
        if not self.settings.enable_local_ai_fallback:
            return scores

        try:
            model = self._load_embedding_model()
        except Exception as exc:
            self.logger.warning("embedding_model_unavailable", reason=str(exc))
            return scores

        try:
            prompt_vector = model.encode(prompt_context.raw_prompt, normalize_embeddings=True)
            for analysis in clip_analyses:
                descriptor = (
                    f"{analysis.asset_type.value} motion {analysis.motion_score} "
                    f"brightness {analysis.brightness} duration {analysis.duration}"
                )
                clip_vector = model.encode(descriptor, normalize_embeddings=True)
                cosine = float(np.dot(prompt_vector, clip_vector))
                scores[analysis.clip_id] = round(scores[analysis.clip_id] + cosine * 2.0, 4)
            return scores
        except Exception as exc:
            raise AIInferenceError(
                message="Semantic scoring failed",
                error_code="semantic_scoring_failed",
                details={"reason": str(exc)},
            ) from exc

    async def _infer_tone(self, prompt: str) -> str:
        keywords = _tokenize(prompt)
        if {"calm", "ambient", "cinematic", "moody"} & set(keywords):
            return "cinematic"
        if {"hype", "energetic", "viral", "fast"} & set(keywords):
            return "energetic"

        if not self.settings.enable_local_ai_fallback:
            return "balanced"

        try:
            classifier = self._load_classifier()
            result = classifier(prompt, truncation=True)[0]
        except Exception as exc:
            self.logger.warning("classifier_unavailable", reason=str(exc))
            return "balanced"

        label = str(result.get("label", "")).lower()
        if "positive" in label:
            return "uplifting"
        if "negative" in label:
            return "dramatic"
        return "balanced"

    def _heuristic_similarity(self, prompt_context: PromptContext, analysis: ClipAnalysis) -> float:
        keywords = set(prompt_context.keywords)
        score = 0.0
        if prompt_context.pacing == "fast":
            score += analysis.motion_score * 5.0
        elif prompt_context.pacing == "slow":
            score += max(0.0, 1.0 - analysis.motion_score) * 3.0
        else:
            score += analysis.motion_score * 2.5

        if {"bright", "sunny", "clean"} & keywords:
            score += min(analysis.brightness / 255.0, 1.0) * 3.0
        if {"dark", "night", "moody"} & keywords:
            score += max(0.0, 1.0 - analysis.brightness / 255.0) * 3.0
        if analysis.asset_type.value in keywords:
            score += 1.0
        score += min(analysis.duration, prompt_context.target_duration) / max(prompt_context.target_duration, 1.0)
        return round(score, 4)

    @lru_cache(maxsize=1)
    def _load_embedding_model(self):
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            self.settings.embedding_model_name,
            cache_folder=str(self.settings.model_cache_dir),
        )

    @lru_cache(maxsize=1)
    def _load_classifier(self):
        from transformers import pipeline

        return pipeline(
            "text-classification",
            model=self.settings.classifier_model_name,
            device=-1,
        )


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9]+", text.lower())


def _infer_pacing(keywords: list[str]) -> str:
    token_set = set(keywords)
    if {"fast", "dynamic", "energetic", "viral", "quick", "hype"} & token_set:
        return "fast"
    if {"slow", "calm", "relaxed", "ambient", "cinematic"} & token_set:
        return "slow"
    return "balanced"


def _infer_target_duration(prompt: str, analyses: list[ClipAnalysis], pacing: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:sec|secs|second|seconds|s)\b", prompt.lower())
    if match:
        return max(3.0, min(60.0, float(match.group(1))))
    base = {"fast": 15.0, "balanced": 20.0, "slow": 30.0}[pacing]
    coverage = sum(min(analysis.duration, 5.0) for analysis in analyses)
    return round(max(6.0, min(45.0, base + math.log1p(coverage) * 2.5)), 2)


def _build_overlay_texts(prompt: str, keywords: list[str]) -> list[str]:
    fragments = [fragment.strip() for fragment in re.split(r"[,.!]", prompt) if fragment.strip()]
    overlays = fragments[:2]
    if not overlays and keywords:
        overlays = [" ".join(keywords[:3]).title()]
    return overlays[:3]
