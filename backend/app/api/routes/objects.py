"""Ontology object routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_link_runtime, get_object_runtime
from app.api.response_contract import build_success_response
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.common import ApiErrorResponse, SuccessResponse
from app.schemas.objects import (
    AggregateLinkedObjectsResponse,
    LinkedObjectsResponse,
    ObjectSearchRequest,
    ObjectSearchResponse,
    OntologyObjectResponse,
)

router = APIRouter()

ObjectRuntimeDependency = Annotated[ObjectRuntime, Depends(get_object_runtime)]
LinkRuntimeDependency = Annotated[LinkRuntime, Depends(get_link_runtime)]


@router.post(
    "/{object_type}/search",
    response_model=SuccessResponse[ObjectSearchResponse],
    responses={
        422: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def search_objects(
    request: Request,
    object_type: str,
    search_request: ObjectSearchRequest,
    runtime: ObjectRuntimeDependency,
) -> SuccessResponse[ObjectSearchResponse]:
    """Search one ontology object type using structured criteria."""
    result = runtime.search_objects(object_type=object_type, request=search_request)
    return build_success_response(
        request,
        result.response,
        next_cursor=result.next_cursor,
        has_more=result.has_more,
    )


@router.get(
    "/{object_type}/{object_id}/links",
    response_model=SuccessResponse[AggregateLinkedObjectsResponse],
    responses={404: {"model": ApiErrorResponse}, 500: {"model": ApiErrorResponse}},
)
def read_object_links(
    request: Request,
    object_type: str,
    object_id: str,
    runtime: LinkRuntimeDependency,
) -> SuccessResponse[AggregateLinkedObjectsResponse]:
    """Return all declared links for one source object."""
    return build_success_response(
        request,
        runtime.get_all_links(
            object_type=object_type,
            object_id=object_id,
        ),
    )


@router.get(
    "/{object_type}/{object_id}/links/{link_type}",
    response_model=SuccessResponse[LinkedObjectsResponse],
    responses={
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
        501: {"model": ApiErrorResponse},
    },
)
def read_linked_objects(
    request: Request,
    object_type: str,
    object_id: str,
    link_type: str,
    runtime: LinkRuntimeDependency,
) -> SuccessResponse[LinkedObjectsResponse]:
    """Return objects linked from one source object through one declared link."""
    return build_success_response(
        request,
        runtime.get_linked_objects(
            object_type=object_type,
            object_id=object_id,
            link_type=link_type,
        ),
    )


@router.get(
    "/{object_type}/{object_id}",
    response_model=SuccessResponse[OntologyObjectResponse],
    responses={404: {"model": ApiErrorResponse}, 500: {"model": ApiErrorResponse}},
)
def read_object(
    request: Request,
    object_type: str,
    object_id: str,
    runtime: ObjectRuntimeDependency,
) -> SuccessResponse[OntologyObjectResponse]:
    """Return one ontology object resolved from trusted registry metadata."""
    return build_success_response(
        request,
        runtime.get_object(object_type=object_type, object_id=object_id),
    )
