# CineSync AI Backend

Production-grade FastAPI backend for a multimodal video orchestration engine that ingests media, analyzes clips, compiles an AI-driven timeline, and renders social-ready outputs through asynchronous pipelines.

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
│   │   └── local.py
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

## Environment Setup

1. Copy the example env file:

```bash
cp .env.example .env
```

2. Adjust values for your environment:

- `DATABASE_URL` for your hosted Postgres instance.
- `AI_SERVER_URL` and `MEDIA_SERVER_URL` for hosted AI or media workers.
- `R2_*` keys for Cloudflare R2.
- Storage and logging paths if you want different mount points.

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

## Troubleshooting

- If `/health` shows FFmpeg as unavailable, verify `FFMPEG_BINARY` and `FFPROBE_BINARY`.
- If uploads fail with `unsupported_mime_type`, update `ALLOWED_MIME_TYPES` and `ALLOWED_EXTENSIONS`.
- If model downloads are restricted, set `ENABLE_LOCAL_AI_FALLBACK=false` to skip transformer loading.
- If OpenCV cannot encode MP4 in your host environment, run through Docker where FFmpeg and the required system libraries are installed.
