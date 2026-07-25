"""Function Engine tests for registry dispatch, validation, and safe failures."""

from __future__ import annotations

from typing import Any

import pytest

from app.functions.registry import FunctionHandlerRegistry, RegisteredFunctionHandler
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    InvocationSource,
    OntologyRole,
)
from app.ontology.loader import load_ontology_registry
from app.runtime.authorization_service import AuthorizationService
from app.runtime.function_engine import (
    FunctionEngine,
    FunctionExecutionFailedError,
    FunctionNotFoundError,
    InvalidFunctionInputError,
    UnregisteredFunctionHandlerError,
)
from app.schemas.functions import (
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityResult,
)


def _actor() -> ActorContext:
    return ActorContext(
        actor_id="test-viewer",
        actor_type=ActorType.HUMAN,
        roles=(OntologyRole.VIEWER,),
        invocation_source=InvocationSource.API,
    )


def _engine(
    *,
    handler_registry: FunctionHandlerRegistry | None = None,
) -> FunctionEngine:
    registry = load_ontology_registry()
    return FunctionEngine(
        registry=registry,
        authorization_service=AuthorizationService(registry.permission_registry),
        handler_registry=handler_registry
        or FunctionHandlerRegistry(
            {
                "getInventoryAvailability": RegisteredFunctionHandler(
                    handler_name="getInventoryAvailability",
                    input_model=GetInventoryAvailabilityParameters,
                    output_model=InventoryAvailabilityResult,
                    execute=lambda _context, _parameters: {
                        "partId": "PART-B",
                        "totalAvailableQuantity": "0.00",
                        "warehouses": [],
                    },
                )
            }
        ),
        session=object(),
    )


def test_function_engine_resolves_public_function_from_ontology_metadata() -> None:
    engine = _engine()

    executed = engine.execute(
        actor=_actor(),
        function_name="getInventoryAvailability",
        raw_parameters={"partId": "PART-B"},
        request_id="req-function-engine",
    )

    assert executed.payload.function_name == "getInventoryAvailability"
    assert executed.payload.result.part_id == "PART-B"
    assert executed.payload.warnings == []


def test_function_engine_dispatches_registered_handler_by_stable_name() -> None:
    calls: list[dict[str, Any]] = []

    def _handler(
        context: Any,
        parameters: GetInventoryAvailabilityParameters,
    ) -> dict[str, Any]:
        calls.append(
            {
                "requestId": context.request_id,
                "partId": parameters.part_id,
            }
        )
        return {
            "partId": parameters.part_id,
            "totalAvailableQuantity": "10.00",
            "warehouses": [],
        }

    engine = _engine(
        handler_registry=FunctionHandlerRegistry(
            {
                "getInventoryAvailability": RegisteredFunctionHandler(
                    handler_name="getInventoryAvailability",
                    input_model=GetInventoryAvailabilityParameters,
                    output_model=InventoryAvailabilityResult,
                    execute=_handler,
                )
            }
        ),
    )

    engine.execute(
        actor=_actor(),
        function_name="getInventoryAvailability",
        raw_parameters={"partId": "PART-B"},
        request_id="req-stable-handler",
    )

    assert calls == [{"requestId": "req-stable-handler", "partId": "PART-B"}]


def test_function_engine_rejects_unknown_function() -> None:
    engine = _engine()

    with pytest.raises(FunctionNotFoundError) as exc_info:
        engine.execute(
            actor=_actor(),
            function_name="unknownFunction",
            raw_parameters={},
            request_id="req-unknown-function",
        )

    assert exc_info.value.code == "FUNCTION_NOT_FOUND"
    assert exc_info.value.status_code == 404


def test_function_engine_rejects_invalid_parameters() -> None:
    engine = _engine()

    with pytest.raises(InvalidFunctionInputError) as exc_info:
        engine.execute(
            actor=_actor(),
            function_name="getInventoryAvailability",
            raw_parameters={"partId": 123},
            request_id="req-invalid-input",
        )

    assert exc_info.value.code == "INVALID_FUNCTION_INPUT"
    assert exc_info.value.status_code == 422
    assert exc_info.value.details["issues"]


def test_function_engine_rejects_unregistered_handler() -> None:
    engine = _engine(handler_registry=FunctionHandlerRegistry({}))

    with pytest.raises(UnregisteredFunctionHandlerError) as exc_info:
        engine.execute(
            actor=_actor(),
            function_name="getInventoryAvailability",
            raw_parameters={"partId": "PART-B"},
            request_id="req-missing-handler",
        )

    assert exc_info.value.code == "UNREGISTERED_FUNCTION_HANDLER"
    assert exc_info.value.status_code == 500


def test_function_engine_validates_handler_output() -> None:
    engine = _engine(
        handler_registry=FunctionHandlerRegistry(
            {
                "getInventoryAvailability": RegisteredFunctionHandler(
                    handler_name="getInventoryAvailability",
                    input_model=GetInventoryAvailabilityParameters,
                    output_model=InventoryAvailabilityResult,
                    execute=lambda _context, _parameters: {"partId": "PART-B"},
                )
            }
        ),
    )

    with pytest.raises(FunctionExecutionFailedError) as exc_info:
        engine.execute(
            actor=_actor(),
            function_name="getInventoryAvailability",
            raw_parameters={"partId": "PART-B"},
            request_id="req-invalid-output",
        )

    assert exc_info.value.code == "FUNCTION_EXECUTION_FAILED"
    assert exc_info.value.status_code == 500


def test_function_engine_maps_unexpected_handler_errors_safely() -> None:
    def _crash(_context: Any, _parameters: Any) -> dict[str, Any]:
        raise RuntimeError("sensitive stack detail")

    engine = _engine(
        handler_registry=FunctionHandlerRegistry(
            {
                "getInventoryAvailability": RegisteredFunctionHandler(
                    handler_name="getInventoryAvailability",
                    input_model=GetInventoryAvailabilityParameters,
                    output_model=InventoryAvailabilityResult,
                    execute=_crash,
                )
            }
        ),
    )

    with pytest.raises(FunctionExecutionFailedError) as exc_info:
        engine.execute(
            actor=_actor(),
            function_name="getInventoryAvailability",
            raw_parameters={"partId": "PART-B"},
            request_id="req-handler-crash",
        )

    assert exc_info.value.code == "FUNCTION_EXECUTION_FAILED"
    assert exc_info.value.message == (
        "Function 'getInventoryAvailability' failed during execution."
    )
