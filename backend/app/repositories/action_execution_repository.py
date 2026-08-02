"""Repository helpers for persisted action execution history."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.action_execution import (
    ActionExecution,
    ActionExecutionInvocationMode,
    ActionExecutionStatus,
)
from app.ontology.actor_context import OntologyRole
from app.schemas.objects import OntologyObjectReference


class ActionExecutionPersistenceError(ApplicationError):
    """Raised when persisted action execution state is missing or inconsistent."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        details: dict[str, object],
        status_code: int,
    ) -> None:
        super().__init__(
            code=code,
            message=message,
            status_code=status_code,
            details=details,
        )


class ActionExecutionRepository:
    """Persist and retrieve action execution rows inside the caller transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_started(
        self,
        *,
        execution_id: str,
        action_type: str,
        action_version: str,
        invocation_mode: ActionExecutionInvocationMode,
        parent_execution_id: str | None,
        actor_id: str,
        actor_role: OntologyRole | str,
        reason: str | None,
        started_at: datetime,
    ) -> ActionExecution:
        execution = ActionExecution(
            execution_id=execution_id,
            action_type=action_type,
            action_version=action_version,
            status=ActionExecutionStatus.STARTED.value,
            invocation_mode=invocation_mode.value,
            parent_execution_id=parent_execution_id,
            actor_id=actor_id,
            actor_role=_normalize_actor_role(actor_role),
            reason=reason,
            started_at=started_at,
            completed_at=None,
            result_payload=None,
            error_code=None,
            error_message=None,
            affected_objects=[],
        )
        self._session.add(execution)
        self._session.flush()
        return execution

    def get_by_execution_id(self, execution_id: str) -> ActionExecution | None:
        statement = self._select_by_execution_id(execution_id)
        return self._session.execute(statement).scalar_one_or_none()

    def mark_succeeded(
        self,
        *,
        execution_id: str,
        completed_at: datetime,
        result_payload: Any,
        affected_objects: Sequence[OntologyObjectReference | Mapping[str, object]],
    ) -> ActionExecution:
        execution = self._get_started_execution_for_update(execution_id)
        execution.status = ActionExecutionStatus.SUCCEEDED.value
        execution.completed_at = completed_at
        execution.result_payload = self._validate_json_compatible(
            execution_id=execution_id,
            field_name="resultPayload",
            payload=result_payload,
        )
        execution.error_code = None
        execution.error_message = None
        execution.affected_objects = self._normalize_affected_objects(affected_objects)
        self._session.flush()
        return execution

    def mark_failed(
        self,
        *,
        execution_id: str,
        completed_at: datetime,
        error_code: str,
        error_message: str,
        affected_objects: Sequence[OntologyObjectReference | Mapping[str, object]],
    ) -> ActionExecution:
        execution = self._get_started_execution_for_update(execution_id)
        execution.status = ActionExecutionStatus.FAILED.value
        execution.completed_at = completed_at
        execution.result_payload = None
        execution.error_code = error_code
        execution.error_message = error_message
        execution.affected_objects = self._normalize_affected_objects(affected_objects)
        self._session.flush()
        return execution

    def _get_started_execution_for_update(self, execution_id: str) -> ActionExecution:
        statement = self._select_by_execution_id(execution_id).with_for_update()
        execution = self._session.execute(statement).scalar_one_or_none()
        if execution is None:
            raise ActionExecutionPersistenceError(
                code="ACTION_EXECUTION_NOT_FOUND",
                message="The action execution was not found.",
                status_code=404,
                details={"executionId": execution_id},
            )
        if execution.status != ActionExecutionStatus.STARTED.value:
            raise ActionExecutionPersistenceError(
                code="ACTION_EXECUTION_ALREADY_FINALIZED",
                message="The action execution is already in a terminal state.",
                status_code=409,
                details={
                    "executionId": execution_id,
                    "status": execution.status,
                },
            )
        return execution

    @staticmethod
    def _select_by_execution_id(execution_id: str) -> Select[tuple[ActionExecution]]:
        return select(ActionExecution).where(ActionExecution.execution_id == execution_id)

    def _normalize_affected_objects(
        self,
        affected_objects: Sequence[OntologyObjectReference | Mapping[str, object]],
    ) -> list[dict[str, str]]:
        normalized: dict[tuple[str, str], dict[str, str]] = {}
        for item in affected_objects:
            if isinstance(item, OntologyObjectReference):
                object_type = item.objectType.strip()
                object_id = item.objectId.strip()
            elif isinstance(item, Mapping):
                raw_object_type = item.get("objectType")
                raw_object_id = item.get("objectId")
                if not isinstance(raw_object_type, str) or not isinstance(raw_object_id, str):
                    continue
                object_type = raw_object_type.strip()
                object_id = raw_object_id.strip()
            else:
                continue
            if not object_type or not object_id:
                continue
            normalized[(object_type, object_id)] = {
                "objectType": object_type,
                "objectId": object_id,
            }
        return [normalized[key] for key in sorted(normalized)]

    def _validate_json_compatible(
        self,
        *,
        execution_id: str,
        field_name: str,
        payload: Any,
    ) -> Any:
        if payload is None or isinstance(payload, (str, int, float, bool)):
            return payload
        if isinstance(payload, list):
            return [
                self._validate_json_compatible(
                    execution_id=execution_id,
                    field_name=field_name,
                    payload=item,
                )
                for item in payload
            ]
        if isinstance(payload, Mapping):
            validated: dict[str, Any] = {}
            for key, value in payload.items():
                if not isinstance(key, str):
                    raise ActionExecutionPersistenceError(
                        code="ACTION_EXECUTION_PERSISTENCE_INCONSISTENCY",
                        message="The action execution payload is not JSON-compatible.",
                        status_code=500,
                        details={
                            "executionId": execution_id,
                            "field": field_name,
                        },
                    )
                validated[key] = self._validate_json_compatible(
                    execution_id=execution_id,
                    field_name=field_name,
                    payload=value,
                )
            return validated
        raise ActionExecutionPersistenceError(
            code="ACTION_EXECUTION_PERSISTENCE_INCONSISTENCY",
            message="The action execution payload is not JSON-compatible.",
            status_code=500,
            details={
                "executionId": execution_id,
                "field": field_name,
            },
        )


def _normalize_actor_role(actor_role: OntologyRole | str) -> str:
    if isinstance(actor_role, OntologyRole):
        return actor_role.value
    return actor_role
