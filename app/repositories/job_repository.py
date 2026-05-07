from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.core.exceptions import ValidationError
from app.models.domain import JobRecord


class InMemoryJobRepository:
    """Async-safe in-memory repository for job state."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: JobRecord) -> JobRecord:
        async with self._lock:
            self._jobs[job.job_id] = job
            return job.model_copy(deep=True)

    async def get(self, job_id: str) -> JobRecord:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValidationError(
                    message=f"Job '{job_id}' not found",
                    error_code="job_not_found",
                )
            return job.model_copy(deep=True)

    async def update(self, job_id: str, **changes: Any) -> JobRecord:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                raise ValidationError(
                    message=f"Job '{job_id}' not found",
                    error_code="job_not_found",
                )
            updated = job.model_copy(
                update={
                    **changes,
                    "updated_at": datetime.utcnow(),
                },
                deep=True,
            )
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)
