"""Ontology metadata routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_ontology_registry
from app.ontology.registry import OntologyRegistry
from app.schemas.common import ApiErrorDetail, ApiErrorResponse
from app.schemas.ontology import (
    OntologyActionTypeCollectionResponse,
    OntologyFunctionCollectionResponse,
    OntologyLinkTypeCollectionResponse,
    OntologyObjectTypeCollectionResponse,
    OntologyObjectTypeDefinition,
    OntologyRoleCollectionResponse,
    OntologySummaryResponse,
)

router = APIRouter()


RegistryDependency = Annotated[OntologyRegistry, Depends(get_ontology_registry)]


def _object_type_not_found_response(object_type: str) -> JSONResponse:
    error = ApiErrorResponse(
        error=ApiErrorDetail(
            code="OBJECT_NOT_FOUND",
            message=f"Object type '{object_type}' was not found.",
            details={"objectType": object_type},
        )
    )
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=error.model_dump(mode="json"),
    )


@router.get("", response_model=OntologySummaryResponse)
def read_ontology_summary(registry: RegistryDependency) -> OntologySummaryResponse:
    """Return a concise summary of the loaded ontology registry."""
    return OntologySummaryResponse(
        key=registry.ontology.key,
        displayName=registry.ontology.displayName,
        version=registry.ontology.version,
        objectTypeCount=len(registry.object_types),
        linkTypeCount=len(registry.link_types),
        functionCount=len(registry.functions),
        actionTypeCount=len(registry.action_types),
        roleCount=len(registry.roles),
    )


@router.get("/object-types", response_model=OntologyObjectTypeCollectionResponse)
def list_object_types(registry: RegistryDependency) -> OntologyObjectTypeCollectionResponse:
    """Return all registered object-type definitions."""
    items = list(registry.object_types)
    return OntologyObjectTypeCollectionResponse(items=items, count=len(items))


@router.get(
    "/object-types/{object_type}",
    response_model=OntologyObjectTypeDefinition,
    responses={404: {"model": ApiErrorResponse}},
)
def read_object_type(
    object_type: str,
    registry: RegistryDependency,
) -> OntologyObjectTypeDefinition | JSONResponse:
    """Return one registered object-type definition by API name."""
    definition = registry.get_object_type(object_type)
    if definition is None:
        return _object_type_not_found_response(object_type)
    return definition


@router.get("/link-types", response_model=OntologyLinkTypeCollectionResponse)
def list_link_types(registry: RegistryDependency) -> OntologyLinkTypeCollectionResponse:
    """Return all registered link-type definitions."""
    items = list(registry.link_types)
    return OntologyLinkTypeCollectionResponse(items=items, count=len(items))


@router.get("/functions", response_model=OntologyFunctionCollectionResponse)
def list_functions(registry: RegistryDependency) -> OntologyFunctionCollectionResponse:
    """Return all registered ontology function definitions."""
    items = list(registry.functions)
    return OntologyFunctionCollectionResponse(items=items, count=len(items))


@router.get("/action-types", response_model=OntologyActionTypeCollectionResponse)
def list_action_types(registry: RegistryDependency) -> OntologyActionTypeCollectionResponse:
    """Return all registered ontology action-type definitions."""
    items = list(registry.action_types)
    return OntologyActionTypeCollectionResponse(items=items, count=len(items))


@router.get("/roles", response_model=OntologyRoleCollectionResponse)
def list_roles(registry: RegistryDependency) -> OntologyRoleCollectionResponse:
    """Return all registered ontology role definitions."""
    items = list(registry.roles)
    return OntologyRoleCollectionResponse(items=items, count=len(items))
