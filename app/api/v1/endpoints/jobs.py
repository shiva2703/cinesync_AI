from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_container
from app.core.container import ApplicationContainer
from app.core.exceptions import ValidationError
from app.schemas.common import SuccessResponse
from app.schemas.jobs import (
    CreateJobRequest,
    JobCreateResponse,
    JobDetailResponse,
    JobOutputResponse,
    JobStatusResponse,
)

router = APIRouter(prefix="/jobs")


@router.post("/create", response_model=JobCreateResponse)
async def create_job(
    payload: CreateJobRequest,
    container: ApplicationContainer = Depends(get_container),
) -> JobCreateResponse:
    for upload_id in payload.upload_ids:
        await container.storage.get_upload(upload_id)
    if payload.audio_upload_id:
        await container.storage.get_upload(payload.audio_upload_id)
    job = await container.job_manager.create_job(
        prompt=payload.prompt,
        upload_ids=payload.upload_ids,
        audio_upload_id=payload.audio_upload_id,
    )
    return JobCreateResponse(job_id=job.job_id, status=job.status, stage=job.stage)


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> JobDetailResponse:
    job = await container.job_manager.get_job(job_id)
    return JobDetailResponse(**job.model_dump())


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> JobStatusResponse:
    job = await container.job_manager.get_job(job_id)
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        stage=job.stage,
        error=job.error,
        updated_at=job.updated_at,
    )


@router.get("/{job_id}/output", response_model=JobOutputResponse)
async def get_job_output(
    job_id: str,
    download: bool = Query(default=False),
    container: ApplicationContainer = Depends(get_container),
) -> JobOutputResponse | FileResponse:
    job = await container.job_manager.get_job(job_id)
    if not job.output_path:
        raise ValidationError("Job output is not yet available", error_code="output_not_ready")
    if download:
        return FileResponse(path=job.output_path, filename=job.output_path.name, media_type="video/mp4")
    return JobOutputResponse(
        job_id=job_id,
        output_path=str(job.output_path),
        timeline_path=job.metadata.get("timeline_path"),
        metadata_path=job.metadata.get("metadata_path"),
    )


@router.delete("/{job_id}", response_model=SuccessResponse)
async def delete_job(
    job_id: str,
    cancel_running: bool = Query(default=True),
    container: ApplicationContainer = Depends(get_container),
) -> SuccessResponse:
    if cancel_running:
        try:
            await container.job_manager.cancel_job(job_id)
        except ValidationError:
            pass
    await container.storage.delete_job(job_id)
    await container.job_manager.delete_job(job_id)
    return SuccessResponse(message=f"Job '{job_id}' deleted")
