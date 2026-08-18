"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.response_contract import (
    REQUEST_ID_HEADER,
    build_error_response,
    build_internal_error_response,
    build_invalid_request_response,
    get_request_id,
    resolve_request_id,
    store_request_id,
)
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError, AuthorizationDeniedError
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.mcp import build_http_identity_resolver, build_mcp_http_app, create_mcp_server
from app.mcp.ontology_tool_gateway import OntologyToolGateway
from app.ontology.loader import load_ontology_registry
from app.ontology.registry import OntologyRegistry
from app.runtime.action_registry import build_action_handler_registry
from app.runtime.authorization_service import AuthorizationService
from app.runtime.function_registry import build_function_handler_registry

logger = logging.getLogger(__name__)

KNOWN_FUNCTION_HANDLERS = {
    "getInventoryAvailability",
    "calculateStockoutRisk",
    "findImpactedParts",
    "findImpactedProducts",
    "findImpactedOrders",
    "rankImpactedOrders",
    "findAlternativeWarehouses",
    "findExpeditablePurchaseOrders",
    "recommendMitigationPlan",
}
KNOWN_ACTION_HANDLERS = {
    "generateMitigationPlan",
    "approveMitigationPlan",
    "reallocateInventory",
    "expeditePurchaseOrder",
}


def _validate_registered_function_handlers(application: FastAPI) -> None:
    handler_registry = application.state.function_handler_registry
    registry = application.state.ontology_registry
    for function_definition in registry.functions:
        if function_definition.handler in KNOWN_FUNCTION_HANDLERS:
            handler_registry.require(function_definition.handler)


def _validate_registered_action_handlers(application: FastAPI) -> None:
    handler_registry = application.state.action_handler_registry
    registry = application.state.ontology_registry
    for action_definition in registry.action_types:
        if action_definition.handler in KNOWN_ACTION_HANDLERS:
            handler_registry.require(action_definition.handler)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize process-wide concerns for the API."""
    configure_logging()
    ontology_registry = load_ontology_registry()
    authorization_service = AuthorizationService(ontology_registry.permission_registry)
    function_handler_registry = build_function_handler_registry()
    action_handler_registry = build_action_handler_registry()
    application.state.ontology_registry = ontology_registry
    application.state.permission_registry = ontology_registry.permission_registry
    application.state.authorization_service = authorization_service
    application.state.function_handler_registry = function_handler_registry
    application.state.action_handler_registry = action_handler_registry
    _validate_registered_function_handlers(application)
    _validate_registered_action_handlers(application)

    if not getattr(application.state, "mcp_remote_enabled", False):
        yield
        return

    mcp_server = getattr(application.state, "mcp_server", None)
    if mcp_server is None:
        yield
        return

    async with mcp_server.session_manager.run():
        yield


def _register_request_id_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def attach_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        store_request_id(request, request_id)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(ApplicationError)
    async def handle_application_error(
        request: Request,
        exc: ApplicationError,
    ) -> JSONResponse:
        request_id = get_request_id(request)
        if isinstance(exc, AuthorizationDeniedError):
            logger.warning(
                "authorization_denied",
                extra={
                    "path": request.url.path,
                    "requestId": request_id,
                    **exc.log_context(),
                },
            )
        return build_error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @application.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "request_validation_failed",
            extra={
                "path": request.url.path,
                "requestId": get_request_id(request),
            },
        )
        return build_invalid_request_response(
            request,
            details={"issues": exc.errors()},
        )

    @application.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            extra={
                "path": request.url.path,
                "requestId": get_request_id(request),
            },
            exc_info=exc,
        )
        return build_internal_error_response(request)


def _build_http_mcp_gateway(application: FastAPI) -> OntologyToolGateway:
    return OntologyToolGateway(
        session_factory=get_session_factory(),
        registry_provider=lambda: cast(OntologyRegistry, application.state.ontology_registry),
        authorization_service_provider=lambda: cast(
            AuthorizationService,
            application.state.authorization_service,
        ),
    )


def _configure_mcp(application: FastAPI, settings: Settings) -> None:
    """Attach the shared MCP server to FastAPI when remote mode is enabled."""
    application.state.mcp_remote_enabled = settings.mcp_remote_enabled
    mcp_server = create_mcp_server(
        settings,
        ontology_tool_gateway=_build_http_mcp_gateway(application),
    )
    application.state.mcp_server = mcp_server
    application.state.mcp_http_identity_resolver = build_http_identity_resolver(settings)

    if not settings.mcp_remote_enabled:
        return

    application.mount(
        "/mcp",
        build_mcp_http_app(
            mcp_server,
            application.state.mcp_http_identity_resolver,
        ),
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
    _configure_mcp(application, settings)
    _register_request_id_middleware(application)
    _register_exception_handlers(application)
    application.include_router(api_router)
    return application


app = create_application()
