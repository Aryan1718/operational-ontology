"""Shared ontology Action Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.actions.registry import (
    ActionHandlerRegistry,
    ActionRegistryError,
    RegisteredActionHandler,
)
from app.core.exceptions import ApplicationError
from app.functions.registry import FunctionHandlerRegistry
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
    TrustedAuthorizationContext,
)
from app.ontology.registry import OntologyRegistry
from app.runtime.authorization_service import AuthorizationService
from app.schemas.actions import ActionExecutionResponse


@dataclass(frozen=True, slots=True)
class ActionExecutionContext:
    """Per-execution trusted action context."""

    session: Session
    registry: OntologyRegistry
    actor: ActorContext
    request_id: str
    executed_at: datetime
    function_handler_registry: FunctionHandlerRegistry
    invocation_mode: Literal["external", "child_action"]
    parent_action_name: str | None
    parent_execution_id: str | None


class ActionNotFoundError(ApplicationError):
    """Raised when a public ontology action key is unknown."""

    def __init__(self, action_name: str) -> None:
        super().__init__(
            code="ACTION_NOT_FOUND",
            message=f"Action '{action_name}' was not found.",
            status_code=404,
            details={"actionName": action_name},
        )


class InvalidActionInputError(ApplicationError):
    """Raised when public action parameters fail validation."""

    def __init__(self, action_name: str, issues: list[Any]) -> None:
        super().__init__(
            code="INVALID_ACTION_INPUT",
            message="The action input is invalid.",
            status_code=422,
            details={"actionName": action_name, "issues": issues},
        )


class UnregisteredActionHandlerError(ApplicationError):
    """Raised when ontology metadata references no executable action handler."""

    def __init__(self, action_name: str, handler_name: str) -> None:
        super().__init__(
            code="UNREGISTERED_ACTION_HANDLER",
            message=f"Action '{action_name}' references an unregistered handler.",
            status_code=500,
            details={"actionName": action_name, "handler": handler_name},
        )


class ActionExecutionFailedError(ApplicationError):
    """Raised when an action handler fails unexpectedly or returns invalid data."""

    def __init__(self, action_name: str) -> None:
        super().__init__(
            code="ACTION_EXECUTION_FAILED",
            message=f"Action '{action_name}' failed during execution.",
            status_code=500,
            details={"actionName": action_name},
        )


class InvalidActionInvocationContextError(ApplicationError):
    """Raised when trusted runtime invocation metadata is inconsistent."""

    def __init__(
        self,
        *,
        invocation_mode: str,
        parent_action_name: str | None,
        parent_execution_id: str | None,
    ) -> None:
        super().__init__(
            code="INVALID_ACTION_INVOCATION_CONTEXT",
            message="The action invocation context is invalid.",
            status_code=500,
            details={
                "invocationMode": invocation_mode,
                "parentActionName": parent_action_name,
                "parentExecutionId": parent_execution_id,
            },
        )


@dataclass(frozen=True, slots=True)
class ExecutedAction:
    """Engine result returned to the route layer."""

    payload: ActionExecutionResponse


class ActionEngine:
    """Resolve, authorize, validate, and execute ontology actions."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        authorization_service: AuthorizationService,
        handler_registry: ActionHandlerRegistry,
        function_handler_registry: FunctionHandlerRegistry,
        session: Session,
    ) -> None:
        self._registry = registry
        self._authorization_service = authorization_service
        self._handler_registry = handler_registry
        self._function_handler_registry = function_handler_registry
        self._session = session

    def execute(
        self,
        *,
        actor: ActorContext,
        action_name: str,
        raw_parameters: dict[str, Any],
        request_id: str,
    ) -> ExecutedAction:
        return self._execute(
            actor=actor,
            action_name=action_name,
            raw_parameters=raw_parameters,
            request_id=request_id,
            invocation_mode="external",
            parent_action_name=None,
            parent_execution_id=None,
        )

    def execute_child_action(
        self,
        *,
        actor: ActorContext,
        action_name: str,
        raw_parameters: dict[str, Any],
        request_id: str | None = None,
        parent_action_name: str,
        parent_execution_id: str,
    ) -> ExecutedAction:
        return self._execute(
            actor=actor,
            action_name=action_name,
            raw_parameters=raw_parameters,
            request_id=request_id or str(uuid4()),
            invocation_mode="child_action",
            parent_action_name=parent_action_name,
            parent_execution_id=parent_execution_id,
        )

    def _execute(
        self,
        *,
        actor: ActorContext,
        action_name: str,
        raw_parameters: dict[str, Any],
        request_id: str,
        invocation_mode: Literal["external", "child_action"],
        parent_action_name: str | None,
        parent_execution_id: str | None,
    ) -> ExecutedAction:
        self._validate_invocation_context(
            invocation_mode=invocation_mode,
            parent_action_name=parent_action_name,
            parent_execution_id=parent_execution_id,
        )
        definition = self._registry.get_action_type(action_name)
        if definition is None:
            raise ActionNotFoundError(action_name)
        trusted_context = self._build_trusted_authorization_context(
            invocation_mode=invocation_mode,
            parent_action_name=parent_action_name,
            parent_execution_id=parent_execution_id,
        )
        self._authorization_service.authorize_or_raise(
            AuthorizationRequest(
                actor=actor,
                capability=AuthorizationCapability.ACTION_EXECUTE,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.ACTION,
                    resource_key=action_name,
                ),
                trusted_context=trusted_context,
            )
        )
        registered_handler = self._require_registered_handler(
            action_name=action_name,
            handler_name=definition.handler,
        )
        parameters = self._validate_input(
            action_name=action_name,
            input_model=registered_handler.input_model,
            raw_parameters=raw_parameters,
        )
        context = ActionExecutionContext(
            session=self._session,
            registry=self._registry,
            actor=actor,
            request_id=request_id,
            executed_at=datetime.now(UTC),
            function_handler_registry=self._function_handler_registry,
            invocation_mode=invocation_mode,
            parent_action_name=parent_action_name,
            parent_execution_id=parent_execution_id,
        )
        try:
            if self._session.in_transaction():
                raw_result = registered_handler.execute(context, parameters)
            else:
                with self._session.begin():
                    raw_result = registered_handler.execute(context, parameters)
        except ApplicationError:
            raise
        except Exception as exc:
            raise ActionExecutionFailedError(action_name) from exc

        result = self._validate_output(
            action_name=action_name,
            output_model=registered_handler.output_model,
            raw_result=raw_result,
        )
        return ExecutedAction(
            payload=ActionExecutionResponse(
                actionName=action_name,
                result=result,
                warnings=getattr(result, "warnings", []),
            )
        )

    @staticmethod
    def _validate_invocation_context(
        *,
        invocation_mode: Literal["external", "child_action"],
        parent_action_name: str | None,
        parent_execution_id: str | None,
    ) -> None:
        if invocation_mode == "external":
            if parent_action_name is not None or parent_execution_id is not None:
                raise InvalidActionInvocationContextError(
                    invocation_mode=invocation_mode,
                    parent_action_name=parent_action_name,
                    parent_execution_id=parent_execution_id,
                )
            return
        if parent_action_name and parent_execution_id:
            return
        raise InvalidActionInvocationContextError(
            invocation_mode=invocation_mode,
            parent_action_name=parent_action_name,
            parent_execution_id=parent_execution_id,
        )

    @staticmethod
    def _build_trusted_authorization_context(
        *,
        invocation_mode: Literal["external", "child_action"],
        parent_action_name: str | None,
        parent_execution_id: str | None,
    ) -> TrustedAuthorizationContext | None:
        if invocation_mode == "external":
            return None
        return TrustedAuthorizationContext(
            internal_dispatch=True,
            parent_action_key=parent_action_name,
            parent_execution_id=parent_execution_id,
        )

    def _require_registered_handler(
        self,
        *,
        action_name: str,
        handler_name: str | None,
    ) -> RegisteredActionHandler:
        normalized_handler_name = handler_name or "<missing>"
        try:
            return self._handler_registry.require(normalized_handler_name)
        except ActionRegistryError as exc:
            raise UnregisteredActionHandlerError(
                action_name,
                normalized_handler_name,
            ) from exc

    @staticmethod
    def _validate_input(
        *,
        action_name: str,
        input_model: type[BaseModel],
        raw_parameters: dict[str, Any],
    ) -> BaseModel:
        try:
            return input_model.model_validate(raw_parameters)
        except ValidationError as exc:
            raise InvalidActionInputError(action_name, exc.errors()) from exc

    @staticmethod
    def _validate_output(
        *,
        action_name: str,
        output_model: Any,
        raw_result: Any,
    ) -> Any:
        try:
            return TypeAdapter(output_model).validate_python(raw_result)
        except ValidationError as exc:
            raise ActionExecutionFailedError(action_name) from exc
