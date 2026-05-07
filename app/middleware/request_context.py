from __future__ import annotations

import uuid
from time import perf_counter

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.utils.context import bind_request_id, clear_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request and log timings."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        bind_request_id(request_id)
        request.state.request_id = request_id
        logger = structlog.get_logger(__name__)
        start = perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((perf_counter() - start) * 1000, 2)
            logger.info(
                "http_request_completed",
                method=request.method,
                path=request.url.path,
                elapsed_ms=elapsed_ms,
                client=request.client.host if request.client else None,
            )
            clear_context()

        response.headers["x-request-id"] = request_id
        return response
