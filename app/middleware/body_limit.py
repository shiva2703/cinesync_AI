from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

from app.config.settings import Settings


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed configured body size based on Content-Length."""

    def __init__(self, app: object, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.settings.max_upload_size:
            request_id = getattr(request.state, "request_id", None) or request.headers.get("x-request-id")
            return JSONResponse(
                status_code=413,
                content={
                    "error_code": "payload_too_large",
                    "message": "Request exceeds maximum upload size",
                    "request_id": request_id,
                    "details": {"max_upload_size": self.settings.max_upload_size},
                },
            )
        return await call_next(request)
