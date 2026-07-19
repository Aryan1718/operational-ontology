"""Ontology object routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_link_runtime, get_object_runtime
from app.runtime.link_runtime import LinkRuntime
from app.runtime.object_runtime import ObjectRuntime
from app.schemas.common import ApiErrorResponse
from app.schemas.objects import LinkedObjectsResponse, OntologyObjectResponse

router = APIRouter()

ObjectRuntimeDependency = Annotated[ObjectRuntime, Depends(get_object_runtime)]
LinkRuntimeDependency = Annotated[LinkRuntime, Depends(get_link_runtime)]


@router.get(
    "/{object_type}/{object_id}/links/{link_type}",
    response_model=LinkedObjectsResponse,
    responses={
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
        501: {"model": ApiErrorResponse},
    },
)
def read_linked_objects(
    object_type: str,
    object_id: str,
    link_type: str,
    runtime: LinkRuntimeDependency,
) -> LinkedObjectsResponse:
    """Return objects linked from one source object through one declared link."""
    return runtime.get_linked_objects(
        object_type=object_type,
        object_id=object_id,
        link_type=link_type,
    )


@router.get(
    "/{object_type}/{object_id}",
    response_model=OntologyObjectResponse,
    responses={404: {"model": ApiErrorResponse}, 500: {"model": ApiErrorResponse}},
)
def read_object(
    object_type: str,
    object_id: str,
    runtime: ObjectRuntimeDependency,
) -> OntologyObjectResponse:
    """Return one ontology object resolved from trusted registry metadata."""
    return runtime.get_object(object_type=object_type, object_id=object_id)
