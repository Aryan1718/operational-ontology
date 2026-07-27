"""Shared FastAPI dependencies."""

from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.actions.registry import ActionHandlerRegistry
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.functions.registry import FunctionHandlerRegistry
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)
from app.ontology.permission_registry import PermissionRegistry
from app.ontology.registry import OntologyRegistry
from app.repositories.object_repository import ObjectRepository
from app.runtime.action_engine import ActionEngine
from app.runtime.authorization_service import AuthorizationService
from app.runtime.function_engine import FunctionEngine
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime

DbSessionDependency = Annotated[Session, Depends(get_db_session)]


def get_app_settings() -> Settings:
    """Provide cached application settings to route handlers."""
    return get_settings()


def get_ontology_registry(request: Request) -> OntologyRegistry:
    """Provide the initialized immutable ontology registry from app state."""
    return cast(OntologyRegistry, request.app.state.ontology_registry)


def get_permission_registry(request: Request) -> PermissionRegistry:
    """Provide the immutable startup-built permission registry from app state."""
    return cast(PermissionRegistry, request.app.state.permission_registry)


def get_authorization_service(request: Request) -> AuthorizationService:
    """Provide the shared central authorization service from app state."""
    return cast(AuthorizationService, request.app.state.authorization_service)


def get_function_handler_registry(request: Request) -> FunctionHandlerRegistry:
    """Provide the immutable function handler registry from app state."""
    return cast(FunctionHandlerRegistry, request.app.state.function_handler_registry)


def get_action_handler_registry(request: Request) -> ActionHandlerRegistry:
    """Provide the immutable action handler registry from app state."""
    return cast(ActionHandlerRegistry, request.app.state.action_handler_registry)


def get_request_actor_context() -> ActorContext:
    """Provide a narrow trusted actor seam until authentication is implemented."""
    return ActorContext(
        actor_id="api-viewer",
        actor_type=ActorType.HUMAN,
        roles=(OntologyRole.VIEWER,),
        invocation_source=InvocationSource.API,
    )


def get_object_runtime(
    request: Request,
    session: DbSessionDependency,
) -> ObjectRuntime:
    """Provide the per-request object runtime backed by the current DB session."""
    registry = get_ontology_registry(request)
    return ObjectRuntime(
        registry=registry,
        repository=ObjectRepository(session),
    )


def get_link_runtime(
    request: Request,
    session: DbSessionDependency,
) -> LinkRuntime:
    """Provide the per-request link runtime backed by the current DB session."""
    registry = get_ontology_registry(request)
    repository = ObjectRepository(session)
    object_runtime = ObjectRuntime(
        registry=registry,
        repository=repository,
    )
    return LinkRuntime(
        registry=registry,
        repository=repository,
        object_runtime=object_runtime,
    )


def get_function_engine(
    request: Request,
    session: DbSessionDependency,
) -> FunctionEngine:
    """Provide the per-request Function Engine backed by the current DB session."""
    return FunctionEngine(
        registry=get_ontology_registry(request),
        authorization_service=get_authorization_service(request),
        handler_registry=get_function_handler_registry(request),
        session=session,
    )


def get_action_engine(
    request: Request,
    session: DbSessionDependency,
) -> ActionEngine:
    """Provide the per-request Action Engine backed by the current DB session."""
    return ActionEngine(
        registry=get_ontology_registry(request),
        authorization_service=get_authorization_service(request),
        handler_registry=get_action_handler_registry(request),
        function_handler_registry=get_function_handler_registry(request),
        session=session,
    )
