from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.config.settings import get_settings
from app.config.validation import validate_environment
from app.core.container import ApplicationContainer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build and tear down shared services for the FastAPI app."""

    settings = get_settings()
    validate_environment(settings)
    container = await ApplicationContainer.build(settings)
    app.state.container = container
    yield
    await container.shutdown()
