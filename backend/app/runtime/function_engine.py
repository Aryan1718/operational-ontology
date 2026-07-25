"""Shared ontology Function Engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError, InvalidOntologyMappingError
from app.functions.registry import (
    FunctionHandlerRegistry,
    FunctionRegistryError,
    RegisteredFunctionHandler,
)
from app.ontology.actor_context import (
    ActorContext,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
)
from app.ontology.registry import OntologyRegistry
from app.runtime.authorization_service import AuthorizationService
from app.schemas.functions import FunctionExecutionResponse


@dataclass(frozen=True, slots=True)
class FunctionExecutionContext:
    """Per-execution read-only runtime context."""

    session: Session
    registry: OntologyRegistry
    request_id: str
    executed_at: datetime


class FunctionNotFoundError(ApplicationError):
    """Raised when a public ontology function key is unknown."""

    def __init__(self, function_name: str) -> None:
        super().__init__(
            code="FUNCTION_NOT_FOUND",
            message=f"Function '{function_name}' was not found.",
            status_code=404,
            details={"functionName": function_name},
        )


class InvalidFunctionInputError(ApplicationError):
    """Raised when public function parameters fail validation."""

    def __init__(self, function_name: str, issues: list[Any]) -> None:
        super().__init__(
            code="INVALID_FUNCTION_INPUT",
            message="The function input is invalid.",
            status_code=422,
            details={"functionName": function_name, "issues": issues},
        )


class UnregisteredFunctionHandlerError(ApplicationError):
    """Raised when ontology metadata references no executable handler."""

    def __init__(self, function_name: str, handler_name: str) -> None:
        super().__init__(
            code="UNREGISTERED_FUNCTION_HANDLER",
            message=f"Function '{function_name}' references an unregistered handler.",
            status_code=500,
            details={"functionName": function_name, "handler": handler_name},
        )


class FunctionExecutionFailedError(ApplicationError):
    """Raised when a function handler fails unexpectedly or returns invalid data."""

    def __init__(self, function_name: str) -> None:
        super().__init__(
            code="FUNCTION_EXECUTION_FAILED",
            message=f"Function '{function_name}' failed during execution.",
            status_code=500,
            details={"functionName": function_name},
        )


@dataclass(frozen=True, slots=True)
class ExecutedFunction:
    """Engine result returned to the route layer."""

    payload: FunctionExecutionResponse


class FunctionEngine:
    """Resolve, authorize, validate, and execute ontology functions."""

    def __init__(
        self,
        *,
        registry: OntologyRegistry,
        authorization_service: AuthorizationService,
        handler_registry: FunctionHandlerRegistry,
        session: Session,
    ) -> None:
        self._registry = registry
        self._authorization_service = authorization_service
        self._handler_registry = handler_registry
        self._session = session

    def execute(
        self,
        *,
        actor: ActorContext,
        function_name: str,
        raw_parameters: dict[str, Any],
        request_id: str,
    ) -> ExecutedFunction:
        definition = self._registry.get_function(function_name)
        if definition is None:
            raise FunctionNotFoundError(function_name)
        if definition.readOnly is not True:
            raise InvalidOntologyMappingError(
                function_name,
                "Function must be marked readOnly for public execution.",
            )
        self._authorization_service.authorize_or_raise(
            AuthorizationRequest(
                actor=actor,
                capability=AuthorizationCapability.FUNCTION_EXECUTE,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.FUNCTION,
                    resource_key=function_name,
                ),
            )
        )
        registered_handler = self._require_registered_handler(
            function_name=function_name,
            handler_name=definition.handler,
        )
        parameters = self._validate_input(
            function_name=function_name,
            input_model=registered_handler.input_model,
            raw_parameters=raw_parameters,
        )
        context = FunctionExecutionContext(
            session=self._session,
            registry=self._registry,
            request_id=request_id,
            executed_at=datetime.now(UTC),
        )
        try:
            raw_result = registered_handler.execute(context, parameters)
        except ApplicationError:
            raise
        except Exception as exc:
            raise FunctionExecutionFailedError(function_name) from exc

        result = self._validate_output(
            function_name=function_name,
            output_model=registered_handler.output_model,
            raw_result=raw_result,
        )
        return ExecutedFunction(
            payload=FunctionExecutionResponse(
                functionName=function_name,
                result=result,
                warnings=[],
            )
        )

    def _require_registered_handler(
        self,
        *,
        function_name: str,
        handler_name: str | None,
    ) -> RegisteredFunctionHandler:
        normalized_handler_name = handler_name or "<missing>"
        try:
            return self._handler_registry.require(normalized_handler_name)
        except FunctionRegistryError as exc:
            raise UnregisteredFunctionHandlerError(
                function_name,
                normalized_handler_name,
            ) from exc

    @staticmethod
    def _validate_input(
        *,
        function_name: str,
        input_model: type[BaseModel],
        raw_parameters: dict[str, Any],
    ) -> BaseModel:
        try:
            return input_model.model_validate(raw_parameters)
        except ValidationError as exc:
            raise InvalidFunctionInputError(function_name, exc.errors()) from exc

    @staticmethod
    def _validate_output(
        *,
        function_name: str,
        output_model: Any,
        raw_result: Any,
    ) -> Any:
        try:
            return TypeAdapter(output_model).validate_python(raw_result)
        except ValidationError as exc:
            raise FunctionExecutionFailedError(function_name) from exc
