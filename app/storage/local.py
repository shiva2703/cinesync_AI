from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from pathlib import Path

import aiofiles
import structlog
from fastapi import UploadFile

from app.config.settings import Settings
from app.core.exceptions import StorageError, ValidationError
from app.models.domain import AssetType, UploadAsset
from app.utils.security import sanitize_filename, validate_upload


class LocalStorage:
    """Local filesystem storage with per-job isolation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = structlog.get_logger(__name__)
        self.root = settings.storage_path
        self.jobs_root = self.root / "jobs"
        self.shared_root = self.root / "shared"
        self.shared_uploads_root = self.shared_root / "uploads"
        self.shared_temp_root = settings.temp_path
        self.shared_outputs_root = settings.output_path
        self.shared_logs_root = self.shared_root / "logs"

    async def initialize(self) -> None:
        for path in [
            self.root,
            self.jobs_root,
            self.shared_root,
            self.shared_uploads_root,
            self.shared_temp_root,
            self.shared_outputs_root,
            self.shared_logs_root,
            self.settings.logs_path,
            self.settings.model_cache_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload_file: UploadFile, job_id: str | None = None) -> UploadAsset:
        filename = validate_upload(upload_file, self.settings)
        upload_id = str(uuid.uuid4())
        asset_type = self._infer_asset_type(filename, upload_file.content_type or "")
        base_directory = self._job_uploads_dir(job_id) if job_id else self.shared_uploads_root / upload_id
        base_directory.mkdir(parents=True, exist_ok=True)
        destination = base_directory / f"{upload_id}{Path(filename).suffix.lower()}"
        size_bytes = 0

        try:
            async with aiofiles.open(destination, "wb") as buffer:
                while True:
                    chunk = await upload_file.read(1024 * 1024)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > self.settings.max_upload_size:
                        raise ValidationError(
                            message="Upload exceeds configured file size limit",
                            error_code="upload_too_large",
                            details={"max_upload_size": self.settings.max_upload_size},
                        )
                    await buffer.write(chunk)
        except Exception as exc:
            if destination.exists():
                destination.unlink(missing_ok=True)
            if isinstance(exc, ValidationError):
                raise
            raise StorageError(
                message="Failed to persist upload",
                error_code="upload_write_failed",
                details={"filename": filename},
            ) from exc
        finally:
            await upload_file.close()

        asset = UploadAsset(
            upload_id=upload_id,
            filename=filename,
            stored_path=destination,
            public_name=sanitize_filename(filename),
            size_bytes=size_bytes,
            mime_type=upload_file.content_type or "",
            extension=Path(filename).suffix.lower(),
            asset_type=asset_type,
        )
        await self._write_asset_manifest(asset)
        self.logger.info(
            "upload_saved",
            upload_id=asset.upload_id,
            filename=asset.filename,
            size_bytes=asset.size_bytes,
            asset_type=asset.asset_type.value,
        )
        return asset

    async def get_upload(self, upload_id: str) -> UploadAsset:
        manifest = self.shared_uploads_root / upload_id / "asset.json"
        if not manifest.exists():
            raise ValidationError(
                message=f"Upload '{upload_id}' not found",
                error_code="upload_not_found",
            )
        async with aiofiles.open(manifest, "r", encoding="utf-8") as file_handle:
            payload = json.loads(await file_handle.read())
        return UploadAsset.model_validate(payload)

    async def create_job_workspace(self, job_id: str) -> dict[str, Path]:
        workspace = {
            "root": self.jobs_root / job_id,
            "uploads": self.jobs_root / job_id / "uploads",
            "temp": self.jobs_root / job_id / "temp",
            "outputs": self.jobs_root / job_id / "outputs",
            "logs": self.jobs_root / job_id / "logs",
        }
        for path in workspace.values():
            path.mkdir(parents=True, exist_ok=True)
        return workspace

    async def stage_uploads_for_job(self, job_id: str, upload_ids: list[str]) -> list[UploadAsset]:
        workspace = await self.create_job_workspace(job_id)
        uploads_dir = workspace["uploads"]
        staged_assets: list[UploadAsset] = []
        for upload_id in upload_ids:
            asset = await self.get_upload(upload_id)
            destination = uploads_dir / asset.stored_path.name
            await asyncio.to_thread(shutil.copy2, asset.stored_path, destination)
            staged_assets.append(
                asset.model_copy(
                    update={"stored_path": destination},
                    deep=True,
                )
            )
        return staged_assets

    async def write_json(self, path: Path, payload: dict | list) -> None:
        safe_path = self._ensure_within_root(path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(safe_path, "w", encoding="utf-8") as file_handle:
            await file_handle.write(json.dumps(payload, indent=2, default=str))

    async def cleanup_job_temp(self, job_id: str) -> None:
        temp_dir = self.jobs_root / job_id / "temp"
        if temp_dir.exists():
            await asyncio.to_thread(shutil.rmtree, temp_dir, True)

    async def delete_job(self, job_id: str) -> None:
        job_dir = self.jobs_root / job_id
        if job_dir.exists():
            await asyncio.to_thread(shutil.rmtree, job_dir, True)

    def get_job_output_file(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "outputs" / "final.mp4"

    def get_job_timeline_file(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "outputs" / "timeline.json"

    def get_job_metadata_file(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "outputs" / "job_metadata.json"

    def get_job_temp_dir(self, job_id: str) -> Path:
        return self.jobs_root / job_id / "temp"

    def _job_uploads_dir(self, job_id: str | None) -> Path:
        if not job_id:
            raise StorageError("Job id is required to access job upload directory", error_code="missing_job_id")
        return self.jobs_root / job_id / "uploads"

    def _infer_asset_type(self, filename: str, mime_type: str) -> AssetType:
        extension = Path(filename).suffix.lower()
        if extension in {".mp4", ".mov", ".mkv", ".avi"} or mime_type.startswith("video/"):
            return AssetType.VIDEO
        if extension in {".png", ".jpg", ".jpeg"} or mime_type.startswith("image/"):
            return AssetType.IMAGE
        if extension in {".wav", ".mp3"} or mime_type.startswith("audio/"):
            return AssetType.AUDIO
        raise ValidationError(
            message=f"Unable to infer asset type for '{filename}'",
            error_code="unsupported_asset_type",
        )

    async def _write_asset_manifest(self, asset: UploadAsset) -> None:
        manifest_path = self.shared_uploads_root / asset.upload_id / "asset.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(manifest_path, "w", encoding="utf-8") as file_handle:
            await file_handle.write(asset.model_dump_json(indent=2))

    def _ensure_within_root(self, path: Path) -> Path:
        resolved = path.resolve()
        root_resolved = self.root.resolve()
        if root_resolved not in resolved.parents and resolved != root_resolved:
            raise StorageError(
                message="Resolved path escapes the storage root",
                error_code="path_traversal_detected",
                details={"path": str(path)},
            )
        return resolved
