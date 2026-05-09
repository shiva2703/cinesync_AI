# CineSync AI Backend

Production-grade FastAPI backend for a multimodal video orchestration engine that ingests media, analyzes clips, compiles an AI-driven timeline, renders social-ready outputs, and persists assets through either local storage or Cloudflare R2.

## Project Structure

```text
.
├── app
│   ├── api
│   │   ├── dependencies.py
│   │   ├── router.py
│   │   └── v1
│   │       ├── endpoints
│   │       │   ├── health.py
│   │       │   ├── jobs.py
│   │       │   └── uploads.py
│   │       └── router.py
│   ├── config
│   │   ├── settings.py
│   │   └── validation.py
│   ├── core
│   │   ├── container.py
│   │   ├── exceptions.py
│   │   └── lifespan.py
│   ├── logging
│   │   └── setup.py
│   ├── middleware
│   │   ├── body_limit.py
│   │   └── request_context.py
│   ├── models
│   │   └── domain.py
│   ├── pipeline
│   │   └── orchestrator.py
│   ├── repositories
│   │   └── job_repository.py
│   ├── schemas
│   │   ├── common.py
│   │   ├── health.py
│   │   ├── jobs.py
│   │   └── uploads.py
│   ├── services
│   │   ├── ai_service.py
│   │   ├── audio_analysis_service.py
│   │   ├── ffmpeg_service.py
│   │   ├── health_service.py
│   │   ├── render_service.py
│   │   ├── timeline_service.py
│   │   └── video_analysis_service.py
│   ├── storage
│   │   ├── base.py
│   │   ├── factory.py
│   │   ├── keys.py
│   │   ├── local.py
│   │   └── r2.py
│   ├── utils
│   │   ├── context.py
│   │   ├── security.py
│   │   └── timers.py
│   ├── workers
│   │   └── job_manager.py
│   └── main.py
├── tests
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_jobs.py
│   └── test_uploads.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
└── requirements.txt
```

## Architecture

The backend is split into production-oriented layers:

- `api/`: versioned HTTP routes and dependency injection.
- `core/`: application lifecycle, exception contracts, and container wiring.
- `config/`: typed environment settings and startup validation.
- `middleware/`: request tracing, request sizing, correlation IDs.
- `services/`: FFmpeg, OpenCV, librosa, AI scoring, timeline compilation, rendering, health.
- `pipeline/`: orchestration across ingestion, analysis, cognition, timeline, and rendering.
- `repositories/`: async-safe in-memory job state repository.
- `storage/`: isolated local storage workspaces for uploads, temp files, outputs, and manifests.
- `workers/`: lightweight async job manager with queueing, cancellation, progress, and timeout handling.

## Features

- Fully async FastAPI service with structured JSON logging via `structlog`.
- Request correlation and job correlation across logs and responses.
- Global exception handling with safe production responses.
- Typed settings using `pydantic-settings` and fail-fast environment validation.
- Upload validation for size, MIME type, extension, and path safety.
- In-memory async job system with status polling and cancellation.
- OpenCV-based clip analysis and composition.
- librosa-based beat detection and timeline alignment.
- FFmpeg/ffprobe async wrapper with retries, timeouts, stderr capture, and metadata extraction.
- Deterministic timeline compiler with optional local transformer-based semantic scoring.
- Dual storage backends:
  - `local` for filesystem-backed development
  - `r2` for Cloudflare R2 persisted uploads and generated outputs
- Deterministic persisted object keys:
  - uploads: `uploads/{scope}/{asset_type}/{base_name}__src__{asset_id}{ext}`
  - outputs: `outputs/{job_id}/{base_name}__final__{output_id}{ext}`
  - timeline: `outputs/{job_id}/{base_name}__timeline__{output_id}.json`
  - metadata: `outputs/{job_id}/{base_name}__meta__{output_id}.json`
  - preview: `outputs/{job_id}/{base_name}__preview__{output_id}.jpg`

## Environment Setup

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Adjust values for your environment:

- `DATABASE_URL` for your hosted Postgres instance.
- `AI_SERVER_URL` and `MEDIA_SERVER_URL` for hosted AI or media workers.
- `STORAGE_BACKEND=local` for local-only persistence, or `STORAGE_BACKEND=r2` for Cloudflare R2.
- `R2_*` keys for Cloudflare R2 when using the R2 backend.
- Storage and logging paths if you want different mount points.

For Cloudflare R2, set:

- `STORAGE_BACKEND=r2`
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`
- `R2_ENDPOINT_URL`
- `R2_PUBLIC_BASE_URL` if you want public asset URLs in API responses

## Local Development

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run tests:

```bash
pytest
```

## Docker Startup

Bring the stack up:

```bash
cp .env.example .env
docker compose up --build
```

API docs are then available at:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## API Endpoints

- `GET /api/v1/health`
- `POST /api/v1/uploads`
- `POST /api/v1/jobs/create`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/jobs/{job_id}/status`
- `GET /api/v1/jobs/{job_id}/output`
- `DELETE /api/v1/jobs/{job_id}`

## Example Requests

Upload media:

```bash
curl -X POST "http://localhost:8000/api/v1/uploads" \
  -F "files=@./sample-assets/clip.mp4" \
  -F "files=@./sample-assets/cover.png"
```

Create a job:

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/create" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a fast 15 second launch teaser with bold text overlays",
    "upload_ids": ["UPLOAD_ID_1", "UPLOAD_ID_2"],
    "audio_upload_id": null
  }'
```

Check status:

```bash
curl "http://localhost:8000/api/v1/jobs/JOB_ID/status"
```

Fetch output metadata:

```bash
curl "http://localhost:8000/api/v1/jobs/JOB_ID/output"
```

When using R2, this response includes:

- `output_object_key`
- `output_public_url`
- `timeline_object_key`
- `metadata_object_key`
- preview keys/URLs when present

Download output:

```bash
curl -L "http://localhost:8000/api/v1/jobs/JOB_ID/output?download=true" --output final.mp4
```

## Logging

Application logs are written to:

- `logs/app.log`
- `logs/errors.log`

Each request and job is tagged with correlation metadata:

- `request_id`
- `job_id`
- elapsed stage timings

## Storage Layout

Shared uploads live under:

```text
storage/shared/uploads/{upload_id}/
```

Each job gets an isolated workspace:

```text
storage/jobs/{job_id}/
├── uploads/
├── temp/
├── outputs/
└── logs/
```

When `STORAGE_BACKEND=r2`, persisted remote object keys follow:

```text
uploads/shared/image/my_ad_creative__src__abc123.png
uploads/shared/video/my_ad_clip__src__def456.mp4
outputs/job789/my_ad_clip__final__ghi999.mp4
outputs/job789/my_ad_clip__timeline__ghi999.json
outputs/job789/my_ad_clip__meta__ghi999.json
outputs/job789/my_ad_clip__preview__ghi999.jpg
```

## Troubleshooting

- If `/health` shows FFmpeg as unavailable, verify `FFMPEG_BINARY` and `FFPROBE_BINARY`.
- If `/health` shows storage connectivity issues in R2 mode, verify `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, and access keys.
- If uploads fail with `unsupported_mime_type`, update `ALLOWED_MIME_TYPES` and `ALLOWED_EXTENSIONS`.
- If model downloads are restricted, set `ENABLE_LOCAL_AI_FALLBACK=false` to skip transformer loading.
- If OpenCV cannot encode MP4 in your host environment, run through Docker where FFmpeg and the required system libraries are installed.
