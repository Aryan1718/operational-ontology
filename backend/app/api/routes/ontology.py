"""Ontology metadata routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_ontology_registry
from app.api.response_contract import build_error_response, build_success_response
from app.ontology.registry import OntologyRegistry
from app.schemas.common import ApiErrorResponse, SuccessResponse
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


def _object_type_not_found_response(request: Request, object_type: str) -> JSONResponse:
    return build_error_response(
        request,
        status_code=status.HTTP_404_NOT_FOUND,
        code="OBJECT_NOT_FOUND",
        message=f"Object type '{object_type}' was not found.",
        details={"objectType": object_type},
    )


@router.get("", response_model=SuccessResponse[OntologySummaryResponse])
def read_ontology_summary(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologySummaryResponse]:
    """Return a concise summary of the loaded ontology registry."""
    return build_success_response(
        request,
        OntologySummaryResponse(
            key=registry.ontology.key,
            displayName=registry.ontology.displayName,
            version=registry.ontology.version,
            objectTypeCount=len(registry.object_types),
            linkTypeCount=len(registry.link_types),
            functionCount=len(registry.functions),
            actionTypeCount=len(registry.action_types),
            roleCount=len(registry.roles),
        ),
    )


@router.get(
    "/object-types",
    response_model=SuccessResponse[OntologyObjectTypeCollectionResponse],
)
def list_object_types(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyObjectTypeCollectionResponse]:
    """Return all registered object-type definitions."""
    items = list(registry.object_types)
    return build_success_response(
        request,
        OntologyObjectTypeCollectionResponse(items=items, count=len(items)),
    )


@router.get(
    "/object-types/{object_type}",
    response_model=SuccessResponse[OntologyObjectTypeDefinition],
    responses={404: {"model": ApiErrorResponse}},
)
def read_object_type(
    request: Request,
    object_type: str,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyObjectTypeDefinition] | JSONResponse:
    """Return one registered object-type definition by API name."""
    definition = registry.get_object_type(object_type)
    if definition is None:
        return _object_type_not_found_response(request, object_type)
    return build_success_response(request, definition)


@router.get(
    "/link-types",
    response_model=SuccessResponse[OntologyLinkTypeCollectionResponse],
)
def list_link_types(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyLinkTypeCollectionResponse]:
    """Return all registered link-type definitions."""
    items = list(registry.link_types)
    return build_success_response(
        request,
        OntologyLinkTypeCollectionResponse(items=items, count=len(items)),
    )


@router.get(
    "/functions",
    response_model=SuccessResponse[OntologyFunctionCollectionResponse],
)
def list_functions(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyFunctionCollectionResponse]:
    """Return all registered ontology function definitions."""
    items = list(registry.functions)
    return build_success_response(
        request,
        OntologyFunctionCollectionResponse(items=items, count=len(items)),
    )


@router.get(
    "/action-types",
    response_model=SuccessResponse[OntologyActionTypeCollectionResponse],
)
def list_action_types(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyActionTypeCollectionResponse]:
    """Return all registered ontology action-type definitions."""
    items = list(registry.action_types)
    return build_success_response(
        request,
        OntologyActionTypeCollectionResponse(items=items, count=len(items)),
    )


@router.get(
    "/roles",
    response_model=SuccessResponse[OntologyRoleCollectionResponse],
)
def list_roles(
    request: Request,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyRoleCollectionResponse]:
    """Return all registered ontology role definitions."""
    items = list(registry.roles)
    return build_success_response(
        request,
        OntologyRoleCollectionResponse(items=items, count=len(items)),
    )
