"""Action execution history routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authorization_service,
    get_db_session,
    get_request_actor_context,
)
from app.api.response_contract import build_success_response
from app.core.exceptions import InvalidRequestError
from app.models.action_execution import ActionExecution
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
)
from app.repositories.action_execution_repository import (
    ActionExecutionListFilters,
    ActionExecutionRepository,
)
from app.runtime.authorization_service import AuthorizationService
from app.schemas.actions import (
    ActionExecutionActorSummary,
    ActionExecutionListResponse,
    ActionExecutionSummary,
)
from app.schemas.common import ApiErrorResponse, SuccessResponse

router = APIRouter()

ActorContextDependency = Annotated[ActorContext, Depends(get_request_actor_context)]
AuthorizationServiceDependency = Annotated[
    AuthorizationService,
    Depends(get_authorization_service),
]
DbSessionDependency = Annotated[Session, Depends(get_db_session)]


@router.get(
    "",
    response_model=SuccessResponse[ActionExecutionListResponse],
    responses={
        401: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def list_action_executions(
    request: Request,
    session: DbSessionDependency,
    actor: ActorContextDependency,
    authorization_service: AuthorizationServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    action_type_id: str | None = Query(default=None, alias="actionTypeId"),
    status: str | None = Query(default=None),
    actor_id: str | None = Query(default=None, alias="actorId"),
    invocation_mode: str | None = Query(default=None, alias="invocationMode"),
    parent_execution_id: str | None = Query(default=None, alias="parentExecutionId"),
) -> SuccessResponse[ActionExecutionListResponse]:
    """Return paginated action execution history using the shared response envelope."""
    _authorize_action_execution_history(actor, authorization_service)
    repository = ActionExecutionRepository(session)
    page = repository.list_execution_summaries(
        filters=ActionExecutionListFilters(
            action_type_id=_normalize_optional_filter("actionTypeId", action_type_id),
            status=_normalize_optional_filter("status", status),
            actor_id=_normalize_optional_filter("actorId", actor_id),
            invocation_mode=_normalize_optional_filter("invocationMode", invocation_mode),
            parent_execution_id=_normalize_optional_filter("parentExecutionId", parent_execution_id),
        ),
        limit=limit,
        cursor=_normalize_cursor(cursor),
    )
    payload = ActionExecutionListResponse(
        executions=[_build_execution_summary(execution) for execution in page.records],
    )
    return build_success_response(
        request,
        payload,
        next_cursor=page.next_cursor,
        has_more=page.has_more,
    )


def _authorize_action_execution_history(
    actor: ActorContext,
    authorization_service: AuthorizationService,
) -> None:
    resource_key = _resolve_action_execution_audit_resource_key(authorization_service)
    authorization_service.authorize_or_raise(
        AuthorizationRequest(
            actor=actor,
            capability=AuthorizationCapability.AUDIT_READ,
            resource=AuthorizationResource(
                resource_type=AuthorizationResourceType.AUDIT_LOG,
                resource_key=resource_key,
            ),
        )
    )


def _resolve_action_execution_audit_resource_key(
    authorization_service: AuthorizationService,
) -> str:
    audit_keys = sorted(
        authorization_service.permission_registry.known_resource_keys_by_type.get(
            AuthorizationResourceType.AUDIT_LOG,
            frozenset(),
        )
    )
    for candidate in audit_keys:
        lowered = candidate.lower()
        if "action" in lowered and ("execution" in lowered or "history" in lowered):
            return candidate
    if len(audit_keys) == 1:
        return audit_keys[0]
    raise InvalidRequestError(
        message="Action execution history authorization is not configured.",
        details={"resourceType": AuthorizationResourceType.AUDIT_LOG.value},
    )


def _build_execution_summary(execution: ActionExecution) -> ActionExecutionSummary:
    return ActionExecutionSummary(
        executionId=execution.execution_id,
        actionTypeId=execution.action_type,
        status=execution.status,
        actor=ActionExecutionActorSummary(
            actorId=execution.actor_id,
            actorRole=execution.actor_role,
        ),
        invocationMode=execution.invocation_mode,
        parentExecutionId=execution.parent_execution_id,
        startedAt=execution.started_at,
        completedAt=execution.completed_at,
        failureCode=execution.error_code,
        failureMessage=execution.error_message,
    )


def _normalize_cursor(raw_cursor: str | None) -> str | None:
    if raw_cursor is None:
        return None
    normalized = raw_cursor.strip()
    if not normalized:
        raise InvalidRequestError(details={"cursor": "Cursor must not be empty."})
    return normalized


def _normalize_optional_filter(field_name: str, raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        raise InvalidRequestError(details={field_name: "Filter values must not be empty."})
    return normalized
