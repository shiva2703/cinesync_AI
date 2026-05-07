from __future__ import annotations

import base64
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADUlEQVR42mP8z/C/HwAF/gL+G4qVYQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def sample_png_bytes() -> bytes:
    return PNG_BYTES


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> AsyncIterator[AsyncClient]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ENABLE_LOCAL_AI_FALLBACK", "false")
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("TEMP_PATH", str(tmp_path / "storage" / "shared" / "temp"))
    monkeypatch.setenv("OUTPUT_PATH", str(tmp_path / "storage" / "shared" / "outputs"))
    monkeypatch.setenv("LOGS_PATH", str(tmp_path / "logs"))
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path / "models-cache"))
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "10485760")
    monkeypatch.setenv("JOB_TIMEOUT_SECONDS", "120")

    from app.config.settings import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app, lifespan="on")

    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    get_settings.cache_clear()
