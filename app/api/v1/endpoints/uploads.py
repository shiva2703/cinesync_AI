from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_container
from app.core.container import ApplicationContainer
from app.schemas.uploads import UploadListResponse, UploadResponse

router = APIRouter(prefix="/uploads")


@router.post("", response_model=UploadListResponse)
async def upload_assets(
    files: list[UploadFile] = File(...),
    container: ApplicationContainer = Depends(get_container),
) -> UploadListResponse:
    uploads = [await container.storage.save_upload(upload_file=file) for file in files]
    return UploadListResponse(
        uploads=[
            UploadResponse(
                upload_id=asset.upload_id,
                filename=asset.filename,
                asset_type=asset.asset_type,
                mime_type=asset.mime_type,
                size_bytes=asset.size_bytes,
                created_at=asset.created_at,
            )
            for asset in uploads
        ]
    )
