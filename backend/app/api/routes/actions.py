"""Governed ontology action routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_action_engine, get_request_actor_context
from app.api.response_contract import build_success_response, get_request_id
from app.ontology.actor_context import ActorContext
from app.runtime.action_engine import ActionEngine
from app.schemas.actions import ActionExecutionRequest, ActionExecutionResponse
from app.schemas.common import ApiErrorResponse, SuccessResponse

router = APIRouter()

ActionEngineDependency = Annotated[ActionEngine, Depends(get_action_engine)]
ActorContextDependency = Annotated[ActorContext, Depends(get_request_actor_context)]


@router.post(
    "/{action_name}",
    response_model=SuccessResponse[ActionExecutionResponse],
    responses={
        403: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def execute_action(
    request: Request,
    action_name: str,
    action_request: ActionExecutionRequest,
    actor: ActorContextDependency,
    engine: ActionEngineDependency,
) -> SuccessResponse[ActionExecutionResponse]:
    """Execute one registered ontology action through the shared action engine."""
    executed = engine.execute(
        actor=actor,
        action_name=_normalize_action_name(action_name),
        raw_parameters=action_request.parameters,
        request_id=get_request_id(request),
    )
    return build_success_response(request, executed.payload)


def _normalize_action_name(raw_action_name: str) -> str:
    normalized = raw_action_name.strip()
    if "-" not in normalized:
        return normalized
    first_segment, *remaining_segments = normalized.split("-")
    return first_segment + "".join(segment.capitalize() for segment in remaining_segments)
