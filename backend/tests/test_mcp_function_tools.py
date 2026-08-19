"""Phase 3 MCP function-tool gateway, registration, and protocol tests."""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthorizationDeniedError
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor
from app.mcp.ontology_tool_gateway import FunctionToolResult, OntologyToolGateway
from app.mcp.server import FUNCTION_TOOL_DEFINITIONS, create_mcp_server
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    AuthorizationCapability,
    AuthorizationDecision,
    AuthorizationReasonCode,
    AuthorizationResourceType,
    InvocationSource,
    OntologyRole,
)
from app.ontology.loader import load_ontology_registry
from app.runtime.authorization_service import AuthorizationService
from app.runtime.function_engine import ExecutedFunction, FunctionEngine
from app.runtime.function_registry import build_function_handler_registry
from app.schemas.functions import FunctionExecutionResponse


@dataclass
class _RecordedExecution:
    actor: ActorContext
    function_name: str
    raw_parameters: dict[str, Any]
    request_id: str


class _StubFunctionEngine:
    def __init__(self) -> None:
        self.calls: list[_RecordedExecution] = []

    def execute(
        self,
        *,
        actor: ActorContext,
        function_name: str,
        raw_parameters: dict[str, Any],
        request_id: str,
    ) -> ExecutedFunction:
        self.calls.append(
            _RecordedExecution(
                actor=actor,
                function_name=function_name,
                raw_parameters=raw_parameters,
                request_id=request_id,
            )
        )
        return ExecutedFunction(
            payload=FunctionExecutionResponse(
                functionName=function_name,
                result={
                    "echo": raw_parameters,
                    "handledBy": "stub-function-engine",
                },
                warnings=[],
            )
        )


class _FunctionGateway(OntologyToolGateway):
    def __init__(self, *, raise_error: bool = False) -> None:
        registry = load_ontology_registry()
        authorization_service = AuthorizationService(registry.permission_registry)
        super().__init__(
            session_factory=lambda: nullcontext(),
            registry_provider=lambda: registry,
            authorization_service_provider=lambda: authorization_service,
        )
        self.engine = _StubFunctionEngine()
        self.raise_error = raise_error
        self.function_calls: list[tuple[str, str, dict[str, Any]]] = []

    def _build_function_engine(self, session):
        del session
        return self.engine

    def execute_function(self, *, actor: ActorContext, function_name: str, payload):
        if self.raise_error:
            raise AuthorizationDeniedError(
                decision=AuthorizationDecision(
                    allowed=False,
                    reason_code=AuthorizationReasonCode.ROLE_NOT_ALLOWED,
                    policy_version="test-policy",
                ),
                capability=AuthorizationCapability.FUNCTION_EXECUTE,
                resource_type=AuthorizationResourceType.FUNCTION,
                resource_key=function_name,
            )
        self.function_calls.append(
            (
                function_name,
                payload.__class__.__name__,
                payload.model_dump(mode="json", by_alias=True),
            )
        )
        return super().execute_function(actor=actor, function_name=function_name, payload=payload)


class _RealSessionGateway(OntologyToolGateway):
    def __init__(self, session) -> None:
        registry = load_ontology_registry()
        authorization_service = AuthorizationService(registry.permission_registry)
        super().__init__(
            session_factory=lambda: nullcontext(session),
            registry_provider=lambda: registry,
            authorization_service_provider=lambda: authorization_service,
        )

    def _build_function_engine(self, session) -> FunctionEngine:
        return FunctionEngine(
            registry=self.registry_provider(),
            authorization_service=self.authorization_service_provider(),
            handler_registry=build_function_handler_registry(),
            session=session,
        )


FUNCTION_SAMPLES: dict[str, dict[str, Any]] = {
    "findImpactedParts": {"riskEventId": "RISK-102"},
    "findImpactedProducts": {"riskEventId": "RISK-102"},
    "findImpactedOrders": {"riskEventId": "RISK-102"},
    "calculateStockoutRisk": {
        "partId": "PART-B",
        "warehouseId": "WH-A",
        "horizonDate": "2026-07-20",
    },
    "getInventoryAvailability": {"partId": "PART-B"},
    "findAlternativeWarehouses": {
        "partId": "PART-B",
        "destinationWarehouseId": "WH-A",
        "requiredQuantity": "40.00",
        "requiredByDate": "2026-07-20",
    },
    "findExpeditablePurchaseOrders": {
        "partId": "PART-E",
        "supplierId": "S-102",
        "requiredByDate": "2026-07-22",
    },
    "rankImpactedOrders": {"riskEventId": "RISK-102"},
    "recommendMitigationPlan": {"riskEventId": "RISK-102"},
}

EXPECTED_TOOL_NAMES = [
    "searchObjects",
    "getObject",
    "getLinkedObjects",
    *[definition.name for definition in FUNCTION_TOOL_DEFINITIONS],
]


def _build_ai_actor() -> ActorContext:
    return ActorContext(
        actor_id="ontology-assistant",
        actor_type=ActorType.AI_AGENT,
        roles=(OntologyRole.AI_AGENT,),
        invocation_source=InvocationSource.MCP,
    )


def _build_unprivileged_ai_actor() -> ActorContext:
    return ActorContext(
        actor_id="untrusted-ai",
        actor_type=ActorType.AI_AGENT,
        roles=(),
        invocation_source=InvocationSource.MCP,
    )


def _build_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def _run_tool_with_actor(*, server, actor: ActorContext, tool_name: str, arguments: dict[str, object]):
    token = set_current_mcp_actor(actor)
    try:
        return asyncio.run(server.call_tool(tool_name, arguments))
    finally:
        reset_current_mcp_actor(token)


def test_gateway_execute_function_reuses_function_engine_path() -> None:
    gateway = _FunctionGateway()

    result = gateway.execute_function(
        actor=_build_ai_actor(),
        function_name="findImpactedOrders",
        payload=FUNCTION_TOOL_DEFINITIONS[2].input_model(**FUNCTION_SAMPLES["findImpactedOrders"]),
    )

    assert gateway.engine.calls == [
        _RecordedExecution(
            actor=_build_ai_actor(),
            function_name="findImpactedOrders",
            raw_parameters={"riskEventId": "RISK-102"},
            request_id="mcp-tool-call",
        )
    ]
    assert result == FunctionToolResult(
        functionName="findImpactedOrders",
        result={
            "echo": {"riskEventId": "RISK-102"},
            "handledBy": "stub-function-engine",
        },
        warnings=[],
    )


def test_http_and_stdio_share_registered_object_and_function_tools() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_FunctionGateway())

    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == EXPECTED_TOOL_NAMES


@pytest.mark.parametrize(
    ("tool_name", "expected_model"),
    [(definition.name, definition.input_model.__name__) for definition in FUNCTION_TOOL_DEFINITIONS],
)
def test_mcp_function_tool_uses_typed_schema_and_canonical_function_name(
    tool_name: str,
    expected_model: str,
) -> None:
    gateway = _FunctionGateway()
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=gateway)

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name=tool_name,
        arguments={"payload": FUNCTION_SAMPLES[tool_name]},
    )

    assert gateway.function_calls == [
        (tool_name, expected_model, FUNCTION_SAMPLES[tool_name])
    ]
    assert structured["functionName"] == tool_name
    assert structured["result"]["echo"] == FUNCTION_SAMPLES[tool_name]
    assert structured["warnings"] == []


def test_mcp_function_tool_maps_application_errors_to_tool_errors() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_FunctionGateway(raise_error=True))

    with pytest.raises(ToolError, match="OPERATION_NOT_PERMITTED"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="findImpactedOrders",
            arguments={"payload": FUNCTION_SAMPLES["findImpactedOrders"]},
        )


def test_mcp_function_tool_rejects_unexpected_trusted_identity_fields() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_FunctionGateway())

    with pytest.raises(Exception, match="extra"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="findImpactedOrders",
            arguments={
                "payload": {
                    "riskEventId": "RISK-102",
                    "actorId": "forged-admin",
                    "actorType": "user",
                    "roles": ["Admin"],
                    "invocationSource": "internal",
                }
            },
        )


def test_mcp_function_tool_cannot_override_authorization_with_arguments() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_FunctionGateway(raise_error=True))

    with pytest.raises(ToolError, match="OPERATION_NOT_PERMITTED"):
        _run_tool_with_actor(
            server=server,
            actor=_build_unprivileged_ai_actor(),
            tool_name="findImpactedOrders",
            arguments={"payload": FUNCTION_SAMPLES["findImpactedOrders"]},
        )


def test_mcp_protocol_invokes_real_find_impacted_orders(database_session) -> None:
    server = create_mcp_server(
        _build_settings(),
        ontology_tool_gateway=_RealSessionGateway(database_session),
    )

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="findImpactedOrders",
        arguments={"payload": FUNCTION_SAMPLES["findImpactedOrders"]},
    )

    assert structured["functionName"] == "findImpactedOrders"
    assert structured["result"]["items"]
    assert structured["result"]["items"][0]["orderId"].startswith("ORD-")


def test_mcp_protocol_invokes_real_recommend_mitigation_plan(database_session) -> None:
    server = create_mcp_server(
        _build_settings(),
        ontology_tool_gateway=_RealSessionGateway(database_session),
    )

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="recommendMitigationPlan",
        arguments={"payload": FUNCTION_SAMPLES["recommendMitigationPlan"]},
    )

    assert structured["functionName"] == "recommendMitigationPlan"
    assert structured["result"]["riskEventId"] == "RISK-102"
    assert structured["result"]["recommendations"]
