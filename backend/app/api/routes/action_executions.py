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
from app.core.exceptions import ApplicationError, InvalidRequestError
from app.models.action_execution import ActionExecution
from app.models.audit_log import AuditLog
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
from app.repositories.audit_repository import AuditRepository
from app.runtime.authorization_service import AuthorizationService
from app.schemas.actions import (
    ActionExecutionActorSummary,
    ActionExecutionDetailResponse,
    ActionExecutionListResponse,
    ActionExecutionSummary,
)
from app.schemas.audit import AuditLogListResponse, AuditLogSummary
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
    offset: int = Query(default=0, ge=0),
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
        offset=offset,
    )
    payload = ActionExecutionListResponse(
        executions=[_build_execution_summary(execution) for execution in page.records],
    )
    return build_success_response(
        request,
        payload,
        next_cursor=None,
        has_more=page.has_more,
    )


@router.get(
    "/{executionId}",
    response_model=SuccessResponse[ActionExecutionDetailResponse],
    responses={
        401: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def get_action_execution(
    executionId: str,
    request: Request,
    session: DbSessionDependency,
    actor: ActorContextDependency,
    authorization_service: AuthorizationServiceDependency,
) -> SuccessResponse[ActionExecutionDetailResponse]:
    """Return one persisted action execution."""
    _authorize_action_execution_history(actor, authorization_service)
    execution = _require_action_execution(ActionExecutionRepository(session), executionId)
    return build_success_response(request, _build_execution_detail(execution))


@router.get(
    "/{executionId}/audit-logs",
    response_model=SuccessResponse[AuditLogListResponse],
    responses={
        401: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def get_action_execution_audit_logs(
    executionId: str,
    request: Request,
    session: DbSessionDependency,
    actor: ActorContextDependency,
    authorization_service: AuthorizationServiceDependency,
) -> SuccessResponse[AuditLogListResponse]:
    """Return audit logs associated with one persisted action execution."""
    _authorize_action_execution_history(actor, authorization_service)
    execution_repository = ActionExecutionRepository(session)
    _require_action_execution(execution_repository, executionId)

    audit_logs = AuditRepository(session).get_by_execution_id(executionId)
    payload = AuditLogListResponse(
        auditLogs=[_build_audit_log_summary(audit_log) for audit_log in audit_logs],
    )
    return build_success_response(request, payload)


def _require_action_execution(
    repository: ActionExecutionRepository,
    execution_id: str,
) -> ActionExecution:
    execution = repository.get_by_execution_id(execution_id)
    if execution is None:
        raise ApplicationError(
            code="ACTION_EXECUTION_NOT_FOUND",
            message="The action execution was not found.",
            status_code=404,
            details={"executionId": execution_id},
        )
    return execution


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


def _build_execution_detail(execution: ActionExecution) -> ActionExecutionDetailResponse:
    return ActionExecutionDetailResponse(
        executionId=execution.execution_id,
        actionTypeId=execution.action_type,
        actionVersion=execution.action_version,
        status=execution.status,
        actor=ActionExecutionActorSummary(
            actorId=execution.actor_id,
            actorRole=execution.actor_role,
        ),
        invocationMode=execution.invocation_mode,
        parentExecutionId=execution.parent_execution_id,
        reason=execution.reason,
        startedAt=execution.started_at,
        completedAt=execution.completed_at,
        resultPayload=execution.result_payload,
        failureCode=execution.error_code,
        failureMessage=execution.error_message,
        affectedObjects=execution.affected_objects,
    )


def _build_audit_log_summary(audit_log: AuditLog) -> AuditLogSummary:
    return AuditLogSummary(
        auditLogId=audit_log.id,
        actionTypeId=audit_log.action_type,
        actorId=audit_log.actor_user_id,
        executionId=audit_log.execution_id,
        objectType=audit_log.object_type,
        objectId=audit_log.object_id,
        previousValue=audit_log.previous_value,
        newValue=audit_log.new_value,
        reason=audit_log.reason,
        timestamp=audit_log.created_at,
    )


def _normalize_optional_filter(field_name: str, raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    normalized = raw_value.strip()
    if not normalized:
        raise InvalidRequestError(details={field_name: "Filter values must not be empty."})
    return normalized
