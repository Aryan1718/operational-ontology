"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ApplicationError, AuthorizationDeniedError
from app.core.logging import configure_logging
from app.ontology.loader import load_ontology_registry
from app.runtime.authorization_service import AuthorizationService
from app.schemas.common import ApiErrorDetail, ApiErrorResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize process-wide concerns for the API."""
    configure_logging()
    ontology_registry = load_ontology_registry()
    authorization_service = AuthorizationService(ontology_registry.permission_registry)
    application.state.ontology_registry = ontology_registry
    application.state.permission_registry = ontology_registry.permission_registry
    application.state.authorization_service = authorization_service
    yield


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        if isinstance(exc, AuthorizationDeniedError):
            logger.warning(
                "authorization_denied",
                extra={
                    "path": request.url.path,
                    **exc.log_context(),
                },
            )
        payload = ApiErrorResponse(
            error=ApiErrorDetail(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
        )


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    application = FastAPI(
        title="Ontology API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_application()
