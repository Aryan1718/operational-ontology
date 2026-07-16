"""Shared FastAPI dependencies."""

from typing import cast

from fastapi import Request

from app.core.config import Settings, get_settings
from app.ontology.permission_registry import PermissionRegistry
from app.ontology.registry import OntologyRegistry
from app.runtime.authorization_service import AuthorizationService


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
