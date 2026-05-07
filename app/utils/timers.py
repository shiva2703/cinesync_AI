from __future__ import annotations

from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator

import structlog


@asynccontextmanager
async def log_timing(event: str, **payload: object) -> AsyncIterator[None]:
    """Log elapsed time for an async operation."""

    logger = structlog.get_logger(__name__)
    start = perf_counter()
    try:
        yield
    finally:
        elapsed_ms = round((perf_counter() - start) * 1000, 2)
        logger.info(event, elapsed_ms=elapsed_ms, **payload)
