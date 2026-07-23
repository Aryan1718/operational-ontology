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
    OntologyActionTypeDefinition,
    OntologyFunctionCollectionResponse,
    OntologyFunctionDefinition,
    OntologyLinkTypeCollectionResponse,
    OntologyLinkTypeDefinition,
    OntologyObjectTypeCollectionResponse,
    OntologyObjectTypeDefinition,
    OntologyRoleCollectionResponse,
    OntologyRoleDefinition,
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


def _metadata_not_found_response(
    request: Request,
    *,
    code: str,
    identifier_key: str,
    identifier_value: str,
    resource_label: str,
) -> JSONResponse:
    return build_error_response(
        request,
        status_code=status.HTTP_404_NOT_FOUND,
        code=code,
        message=f"{resource_label} '{identifier_value}' was not found.",
        details={identifier_key: identifier_value},
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
    "/link-types/{link_type}",
    response_model=SuccessResponse[OntologyLinkTypeDefinition],
    responses={404: {"model": ApiErrorResponse}},
)
def read_link_type(
    request: Request,
    link_type: str,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyLinkTypeDefinition] | JSONResponse:
    """Return one registered link-type definition by API name."""
    definition = registry.get_link_type(link_type)
    if definition is None:
        return _metadata_not_found_response(
            request,
            code="LINK_NOT_FOUND",
            identifier_key="linkType",
            identifier_value=link_type,
            resource_label="Link type",
        )
    return build_success_response(request, definition)


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
    "/functions/{function_key}",
    response_model=SuccessResponse[OntologyFunctionDefinition],
    responses={404: {"model": ApiErrorResponse}},
)
def read_function(
    request: Request,
    function_key: str,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyFunctionDefinition] | JSONResponse:
    """Return one registered function definition by API name."""
    definition = registry.get_function(function_key)
    if definition is None:
        return _metadata_not_found_response(
            request,
            code="FUNCTION_NOT_FOUND",
            identifier_key="function",
            identifier_value=function_key,
            resource_label="Function",
        )
    return build_success_response(request, definition)


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
    "/action-types/{action_type}",
    response_model=SuccessResponse[OntologyActionTypeDefinition],
    responses={404: {"model": ApiErrorResponse}},
)
def read_action_type(
    request: Request,
    action_type: str,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyActionTypeDefinition] | JSONResponse:
    """Return one registered action-type definition by API name."""
    definition = registry.get_action_type(action_type)
    if definition is None:
        return _metadata_not_found_response(
            request,
            code="ACTION_NOT_FOUND",
            identifier_key="actionType",
            identifier_value=action_type,
            resource_label="Action type",
        )
    return build_success_response(request, definition)


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


@router.get(
    "/roles/{role_key}",
    response_model=SuccessResponse[OntologyRoleDefinition],
    responses={404: {"model": ApiErrorResponse}},
)
def read_role(
    request: Request,
    role_key: str,
    registry: RegistryDependency,
) -> SuccessResponse[OntologyRoleDefinition] | JSONResponse:
    """Return one registered ontology role definition by API name."""
    definition = registry.get_role(role_key)
    if definition is None:
        return _metadata_not_found_response(
            request,
            code="ROLE_NOT_FOUND",
            identifier_key="role",
            identifier_value=role_key,
            resource_label="Role",
        )
    return build_success_response(request, definition)
