"""Audit log history routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_authorization_service,
    get_db_session,
    get_request_actor_context,
)
from app.api.response_contract import build_success_response
from app.core.exceptions import InvalidRequestError
from app.models.audit_log import AuditLog
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
)
from app.repositories.audit_repository import AuditLogListFilters, AuditRepository
from app.runtime.authorization_service import AuthorizationService
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
    response_model=SuccessResponse[AuditLogListResponse],
    responses={
        401: {"model": ApiErrorResponse},
        403: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
def list_audit_logs(
    request: Request,
    session: DbSessionDependency,
    actor: ActorContextDependency,
    authorization_service: AuthorizationServiceDependency,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    object_type: str | None = Query(default=None, alias="objectType"),
    object_id: UUID | None = Query(default=None, alias="objectId"),
    actor_id: UUID | None = Query(default=None, alias="actorId"),
    action_type_id: str | None = Query(default=None, alias="actionTypeId"),
) -> SuccessResponse[AuditLogListResponse]:
    """Return paginated persisted audit log history using the shared response envelope."""
    _authorize_audit_log_history(actor, authorization_service)
    repository = AuditRepository(session)
    page = repository.list_audit_logs(
        filters=AuditLogListFilters(
            object_type=_normalize_optional_filter("objectType", object_type),
            object_id=object_id,
            actor_id=actor_id,
            action_type_id=_normalize_optional_filter("actionTypeId", action_type_id),
        ),
        limit=limit,
        offset=offset,
    )
    payload = AuditLogListResponse(
        auditLogs=[_build_audit_log_summary(audit_log) for audit_log in page.records],
    )
    return build_success_response(
        request,
        payload,
        next_cursor=None,
        has_more=page.has_more,
    )


def _authorize_audit_log_history(
    actor: ActorContext,
    authorization_service: AuthorizationService,
) -> None:
    resource_key = _resolve_audit_log_resource_key(authorization_service)
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


def _resolve_audit_log_resource_key(
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
        if "audit" in lowered and ("log" in lowered or "history" in lowered):
            return candidate
    if len(audit_keys) == 1:
        return audit_keys[0]
    raise InvalidRequestError(
        message="Audit log history authorization is not configured.",
        details={"resourceType": AuthorizationResourceType.AUDIT_LOG.value},
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
