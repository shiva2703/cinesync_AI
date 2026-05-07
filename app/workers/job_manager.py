from __future__ import annotations

import asyncio
import uuid

import structlog

from app.config.settings import Settings
from app.models.domain import JobRecord, JobStatus
from app.repositories.job_repository import InMemoryJobRepository
from app.utils.context import bind_job_id


class InMemoryJobManager:
    """Background job execution with status tracking and cancellation."""

    def __init__(
        self,
        settings: Settings,
        repository: InMemoryJobRepository,
        pipeline_orchestrator,
    ) -> None:
        self.settings = settings
        self.repository = repository
        self.pipeline_orchestrator = pipeline_orchestrator
        self.logger = structlog.get_logger(__name__)
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def create_job(self, prompt: str, upload_ids: list[str], audio_upload_id: str | None = None) -> JobRecord:
        job_id = str(uuid.uuid4())
        job = JobRecord(
            job_id=job_id,
            status=JobStatus.QUEUED,
            prompt=prompt,
            upload_ids=upload_ids,
            audio_upload_id=audio_upload_id,
        )
        await self.repository.create(job)
        task = asyncio.create_task(self._run_job(job_id), name=f"job-{job_id}")
        self._tasks[job_id] = task
        return job

    async def get_job(self, job_id: str) -> JobRecord:
        return await self.repository.get(job_id)

    async def cancel_job(self, job_id: str) -> JobRecord:
        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return await self.repository.update(
            job_id,
            status=JobStatus.CANCELLED,
            stage="cancelled",
            error="Job cancelled by client",
        )

    async def delete_job(self, job_id: str) -> None:
        task = self._tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.repository.delete(job_id)

    async def shutdown(self) -> None:
        active = [task for task in self._tasks.values() if not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

    async def _run_job(self, job_id: str) -> None:
        bind_job_id(job_id)
        await self.repository.update(job_id, status=JobStatus.PROCESSING, stage="processing", progress=0.01)
        try:
            await asyncio.wait_for(
                self.pipeline_orchestrator.run(job_id),
                timeout=self.settings.job_timeout_seconds,
            )
        except asyncio.CancelledError:
            self.logger.warning("job_cancelled", job_id=job_id)
            await self.repository.update(
                job_id,
                status=JobStatus.CANCELLED,
                stage="cancelled",
                error="Job cancelled by client",
            )
            raise
        except asyncio.TimeoutError:
            self.logger.exception("job_timeout", job_id=job_id)
            await self.repository.update(
                job_id,
                status=JobStatus.FAILED,
                stage="failed",
                error="Job exceeded execution timeout",
            )
        except Exception as exc:
            self.logger.exception("job_failed", job_id=job_id, error=str(exc))
            await self.repository.update(
                job_id,
                status=JobStatus.FAILED,
                stage="failed",
                error=str(exc),
            )
        else:
            await self.repository.update(job_id, status=JobStatus.COMPLETED)
        finally:
            self._tasks.pop(job_id, None)
