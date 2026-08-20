from __future__ import annotations

import asyncio
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError, AuthorizationDeniedError
from app.mcp.context import reset_current_mcp_actor, set_current_mcp_actor
from app.mcp.ontology_tool_gateway import OntologyToolGateway
from app.mcp.server import FUNCTION_TOOL_DEFINITIONS, create_mcp_server
from app.models.mitigation import MitigationPlan
from app.ontology.actor_context import (
    ActorContext,
    ActorType,
    AuthorizationCapability,
    AuthorizationRequest,
    AuthorizationResource,
    AuthorizationResourceType,
    InvocationSource,
    OntologyRole,
)
from app.ontology.loader import load_ontology_registry
from app.repositories.action_execution_repository import ActionExecutionRepository
from app.repositories.audit_repository import AuditRepository
from app.runtime.action_engine import ExecutedAction
from app.runtime.authorization_service import AuthorizationService
from app.schemas.actions import ActionExecutionResponse, GenerateMitigationPlanParameters


@dataclass
class _RecordedActionExecution:
    actor: ActorContext
    action_name: str
    raw_parameters: dict[str, Any]
    request_id: str


class _StubActionEngine:
    def __init__(self, *, raise_error: ApplicationError | None = None) -> None:
        self.raise_error = raise_error
        self.calls: list[_RecordedActionExecution] = []

    def execute(
        self,
        *,
        actor: ActorContext,
        action_name: str,
        raw_parameters: dict[str, Any],
        request_id: str,
    ) -> ExecutedAction:
        self.calls.append(
            _RecordedActionExecution(
                actor=actor,
                action_name=action_name,
                raw_parameters=raw_parameters,
                request_id=request_id,
            )
        )
        if self.raise_error is not None:
            raise self.raise_error
        return ExecutedAction(
            payload=ActionExecutionResponse(
                actionName=action_name,
                result={
                    "mitigationPlanId": "MIT-TEST-001",
                    "riskEventId": raw_parameters["riskEventId"],
                    "status": "draft",
                },
                warnings=["human review required"],
            )
        )


class _ActionGateway(OntologyToolGateway):
    def __init__(self, *, raise_error: ApplicationError | None = None) -> None:
        registry = load_ontology_registry()
        authorization_service = AuthorizationService(registry.permission_registry)
        super().__init__(
            session_factory=lambda: nullcontext(),
            registry_provider=lambda: registry,
            authorization_service_provider=lambda: authorization_service,
        )
        self.engine = _StubActionEngine(raise_error=raise_error)

    def _build_action_engine(self, session):
        del session
        return self.engine


class _RealSessionGateway(OntologyToolGateway):
    def __init__(self, session) -> None:
        registry = load_ontology_registry()
        authorization_service = AuthorizationService(registry.permission_registry)
        super().__init__(
            session_factory=lambda: nullcontext(session),
            registry_provider=lambda: registry,
            authorization_service_provider=lambda: authorization_service,
        )


def _build_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


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


def _build_escalation_attempt_actor() -> ActorContext:
    return ActorContext(
        actor_id="ai-with-admin-role",
        actor_type=ActorType.AI_AGENT,
        roles=(OntologyRole.AI_AGENT, OntologyRole.ADMIN, OntologyRole.OPERATIONS_MANAGER),
        invocation_source=InvocationSource.MCP,
    )


def _run_tool_with_actor(*, server, actor: ActorContext, tool_name: str, arguments: dict[str, object]):
    token = set_current_mcp_actor(actor)
    try:
        return asyncio.run(server.call_tool(tool_name, arguments))
    finally:
        reset_current_mcp_actor(token)


def test_generate_mitigation_plan_is_registered_and_downstream_actions_are_not() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_ActionGateway())

    tools = asyncio.run(server.list_tools())
    tool_names = [tool.name for tool in tools]

    assert tool_names == [
        "searchObjects",
        "getObject",
        "getLinkedObjects",
        *[definition.name for definition in FUNCTION_TOOL_DEFINITIONS],
        "generateMitigationPlan",
    ]
    assert "approveMitigationPlan" not in tool_names
    assert "reallocateInventory" not in tool_names
    assert "expeditePurchaseOrder" not in tool_names
    assert "executeMitigationPlan" not in tool_names
    assert "resolveRiskEvent" not in tool_names


def test_gateway_execute_generate_mitigation_plan_reuses_action_engine_path() -> None:
    gateway = _ActionGateway()

    result = gateway.execute_generate_mitigation_plan(
        actor=_build_ai_actor(),
        payload=GenerateMitigationPlanParameters(riskEventId="RISK-102"),
        request_id="mcp-generate-001",
    )

    assert gateway.engine.calls == [
        _RecordedActionExecution(
            actor=_build_ai_actor(),
            action_name="generateMitigationPlan",
            raw_parameters={"riskEventId": "RISK-102", "strategyPreference": None, "notes": None},
            request_id="mcp-generate-001",
        )
    ]
    assert result.model_dump(mode="json", by_alias=True) == {
        "executionId": "mcp-generate-001",
        "actionTypeId": "generateMitigationPlan",
        "status": "succeeded",
        "result": {
            "mitigationPlanId": "MIT-TEST-001",
            "riskEventId": "RISK-102",
            "status": "draft",
        },
        "warnings": ["human review required"],
    }


def test_mcp_action_tool_uses_typed_schema_and_trusted_actor_context(monkeypatch: pytest.MonkeyPatch) -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_ActionGateway())

    def _direct_handler_should_not_run(*args, **kwargs):
        raise AssertionError("MCP must use ActionEngine, not the handler directly.")

    monkeypatch.setattr(
        "app.actions.generate_mitigation_plan.generate_mitigation_plan",
        _direct_handler_should_not_run,
    )

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="generateMitigationPlan",
        arguments={"payload": {"riskEventId": "RISK-102"}},
    )

    assert structured["actionTypeId"] == "generateMitigationPlan"
    assert structured["status"] == "succeeded"
    assert structured["result"]["riskEventId"] == "RISK-102"


def test_mcp_action_tool_maps_application_errors_to_tool_errors() -> None:
    server = create_mcp_server(
        _build_settings(),
        ontology_tool_gateway=_ActionGateway(
            raise_error=ApplicationError(
                code="INVALID_RISK_EVENT_STATE",
                message="The risk event is not in a state that allows mitigation planning.",
                status_code=409,
            )
        ),
    )

    with pytest.raises(ToolError, match="INVALID_RISK_EVENT_STATE"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="generateMitigationPlan",
            arguments={"payload": {"riskEventId": "RISK-102"}},
        )


def test_mcp_action_tool_rejects_unexpected_trusted_identity_fields() -> None:
    server = create_mcp_server(_build_settings(), ontology_tool_gateway=_ActionGateway())

    with pytest.raises(Exception, match="extra"):
        _run_tool_with_actor(
            server=server,
            actor=_build_ai_actor(),
            tool_name="generateMitigationPlan",
            arguments={
                "payload": {
                    "riskEventId": "RISK-102",
                    "actorId": "admin",
                    "actorType": "user",
                    "roles": ["Admin"],
                    "permissions": ["approveMitigationPlan"],
                    "invocationSource": "ui",
                    "executionId": "forged",
                    "parentExecutionId": "forged-parent",
                }
            },
        )


def test_unprivileged_ai_actor_cannot_execute_generate_mitigation_plan() -> None:
    registry = load_ontology_registry()
    service = AuthorizationService(registry.permission_registry)

    with pytest.raises(AuthorizationDeniedError):
        service.authorize_or_raise(
            AuthorizationRequest(
                actor=_build_unprivileged_ai_actor(),
                capability=AuthorizationCapability.ACTION_EXECUTE,
                resource=AuthorizationResource(
                    resource_type=AuthorizationResourceType.ACTION,
                    resource_key="generateMitigationPlan",
                ),
            )
        )


def test_ai_agent_permission_is_narrowly_scoped_to_generate_mitigation_plan() -> None:
    registry = load_ontology_registry()
    service = AuthorizationService(registry.permission_registry)
    actor = _build_escalation_attempt_actor()

    allowed = service.authorize_or_raise(
        AuthorizationRequest(
            actor=actor,
            capability=AuthorizationCapability.ACTION_EXECUTE,
            resource=AuthorizationResource(
                resource_type=AuthorizationResourceType.ACTION,
                resource_key="generateMitigationPlan",
            ),
        )
    )

    assert allowed.allowed is True

    for action_name in ["approveMitigationPlan", "reallocateInventory", "expeditePurchaseOrder"]:
        with pytest.raises(AuthorizationDeniedError):
            service.authorize_or_raise(
                AuthorizationRequest(
                    actor=actor,
                    capability=AuthorizationCapability.ACTION_EXECUTE,
                    resource=AuthorizationResource(
                        resource_type=AuthorizationResourceType.ACTION,
                        resource_key=action_name,
                    ),
                )
            )


def test_mcp_protocol_invokes_real_generate_mitigation_plan_and_persists_execution(database_session) -> None:
    server = create_mcp_server(
        _build_settings(),
        ontology_tool_gateway=_RealSessionGateway(database_session),
    )

    _, structured = _run_tool_with_actor(
        server=server,
        actor=_build_ai_actor(),
        tool_name="generateMitigationPlan",
        arguments={"payload": {"riskEventId": "RISK-102"}},
    )

    execution_id = structured["executionId"]
    mitigation_plan_id = structured["result"]["mitigationPlanId"]

    plan = database_session.execute(
        select(MitigationPlan).where(MitigationPlan.mitigation_code == mitigation_plan_id)
    ).scalar_one()
    execution = ActionExecutionRepository(database_session).get_by_execution_id(execution_id)
    audit_logs = AuditRepository(database_session).get_by_execution_id(execution_id)

    assert structured["actionTypeId"] == "generateMitigationPlan"
    assert structured["status"] == "succeeded"
    assert structured["result"]["status"] == "draft"
    assert execution is not None
    assert execution.action_type == "generateMitigationPlan"
    assert execution.actor_id == "ontology-assistant"
    assert execution.actor_role == "AIAgent"
    assert execution.invocation_mode == "direct"
    assert execution.parent_execution_id is None
    assert execution.status == "succeeded"
    assert plan.status == "draft"
    assert plan.approved_by is None
    assert plan.approved_at is None
    assert audit_logs
    assert {audit_log.execution_id for audit_log in audit_logs} == {execution_id}
    assert {audit_log.action_type for audit_log in audit_logs} == {"generateMitigationPlan"}
