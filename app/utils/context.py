from __future__ import annotations

from contextvars import ContextVar
from typing import Iterator

import structlog

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
job_id_context: ContextVar[str | None] = ContextVar("job_id", default=None)


def bind_request_id(request_id: str) -> None:
    request_id_context.set(request_id)
    structlog.contextvars.bind_contextvars(request_id=request_id)


def bind_job_id(job_id: str) -> None:
    job_id_context.set(job_id)
    structlog.contextvars.bind_contextvars(job_id=job_id)


def clear_context() -> None:
    request_id_context.set(None)
    job_id_context.set(None)
    structlog.contextvars.clear_contextvars()


def get_request_id() -> str | None:
    return request_id_context.get()


def get_job_id() -> str | None:
    return job_id_context.get()
