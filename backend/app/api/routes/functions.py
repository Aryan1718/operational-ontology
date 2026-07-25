"""Read-only ontology function routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_function_engine, get_request_actor_context
from app.api.response_contract import build_success_response, get_request_id
from app.ontology.actor_context import ActorContext
from app.runtime.function_engine import FunctionEngine
from app.schemas.common import ApiErrorResponse, SuccessResponse
from app.schemas.functions import FunctionExecutionRequest, FunctionExecutionResponse

router = APIRouter()

FunctionEngineDependency = Annotated[FunctionEngine, Depends(get_function_engine)]
ActorContextDependency = Annotated[ActorContext, Depends(get_request_actor_context)]


@router.post(
    '/{function_name}/execute',
    response_model=SuccessResponse[FunctionExecutionResponse],
    responses={
        404: {'model': ApiErrorResponse},
        422: {'model': ApiErrorResponse},
        500: {'model': ApiErrorResponse},
    },
)
def execute_function(
    request: Request,
    function_name: str,
    function_request: FunctionExecutionRequest,
    actor: ActorContextDependency,
    engine: FunctionEngineDependency,
) -> SuccessResponse[FunctionExecutionResponse]:
    """Execute one registered read-only ontology function."""
    executed = engine.execute(
        actor=actor,
        function_name=function_name,
        raw_parameters=function_request.parameters,
        request_id=get_request_id(request),
    )
    return build_success_response(request, executed.payload)
