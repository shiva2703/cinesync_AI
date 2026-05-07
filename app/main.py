from __future__ import annotations

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import router as api_router
from app.config.settings import get_settings
from app.core.exceptions import AppError
from app.core.lifespan import lifespan
from app.middleware.body_limit import BodySizeLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.common import ErrorResponse


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(BodySizeLimitMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger = structlog.get_logger(__name__)
        logger.error(
            "application_error",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=exc.error_code,
                message=exc.message,
                request_id=getattr(request.state, "request_id", None),
                details=exc.details,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger = structlog.get_logger(__name__)
        logger.error("request_validation_error", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="request_validation_error",
                message="Request validation failed",
                request_id=getattr(request.state, "request_id", None),
                details={"errors": exc.errors()},
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger = structlog.get_logger(__name__)
        logger.exception("unhandled_exception", exception_type=type(exc).__name__)
        message = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error_code="internal_server_error",
                message=message,
                request_id=getattr(request.state, "request_id", None),
            ).model_dump(mode="json"),
        )

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": f"{settings.app_name} backend is running"}

    return app


app = create_app()
