from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient

from app.api.dependencies import get_request_actor_context
from app.api.response_contract import REQUEST_ID_HEADER
from app.db.session import get_session_factory
from app.ontology.actor_context import ActorContext, ActorType, InvocationSource, OntologyRole
from app.repositories.action_execution_repository import (
    ActionExecutionListFilters,
    ActionExecutionRepository,
)
from app.repositories.audit_repository import AuditRepository


def _planner_actor() -> ActorContext:
    return ActorContext(
        actor_id="planner-user-1",
        actor_type=ActorType.HUMAN,
        roles=(OntologyRole.PLANNER,),
        invocation_source=InvocationSource.API,
    )


def _operations_manager_actor() -> ActorContext:
    return ActorContext(
        actor_id="ops-manager-1",
        actor_type=ActorType.HUMAN,
        roles=(OntologyRole.OPERATIONS_MANAGER,),
        invocation_source=InvocationSource.API,
    )


def _use_actor(client: TestClient, actor: ActorContext) -> Generator[None, None, None]:
    client.app.dependency_overrides[get_request_actor_context] = lambda: actor
    try:
        yield
    finally:
        client.app.dependency_overrides.pop(get_request_actor_context, None)


def test_generate_mitigation_plan_route_persists_action_execution_and_audit_linkage(database_client) -> None:
    request_id = "exec-generate-001"

    override = _use_actor(database_client, _planner_actor())
    next(override)
    try:
        response = database_client.post(
            "/api/v1/actions/generateMitigationPlan",
            headers={REQUEST_ID_HEADER: request_id},
            json={"parameters": {"riskEventId": "RISK-102"}},
        )
    finally:
        try:
            next(override)
        except StopIteration:
            pass

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["actionName"] == "generateMitigationPlan"
    assert body["result"]["status"] == "draft"

    with get_session_factory()() as session:
        execution = ActionExecutionRepository(session).get_by_execution_id(request_id)
        assert execution is not None
        assert execution.action_type == "generateMitigationPlan"
        assert execution.actor_id == "planner-user-1"
        assert execution.actor_role == "Planner"
        assert execution.invocation_mode == "direct"
        assert execution.parent_execution_id is None
        assert execution.status == "succeeded"
        assert execution.completed_at is not None

        audit_logs = AuditRepository(session).get_by_execution_id(request_id)
        assert audit_logs
        assert {audit_log.action_type for audit_log in audit_logs} == {"generateMitigationPlan"}
        assert {audit_log.execution_id for audit_log in audit_logs} == {request_id}


def test_generate_mitigation_plan_route_persists_failed_action_execution(database_client) -> None:
    request_id = "exec-generate-failure-001"

    override = _use_actor(database_client, _planner_actor())
    next(override)
    try:
        response = database_client.post(
            "/api/v1/actions/generateMitigationPlan",
            headers={REQUEST_ID_HEADER: request_id},
            json={"parameters": {"riskEventId": "RISK-DOES-NOT-EXIST"}},
        )
    finally:
        try:
            next(override)
        except StopIteration:
            pass

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RISK_EVENT_NOT_FOUND"

    with get_session_factory()() as session:
        execution = ActionExecutionRepository(session).get_by_execution_id(request_id)
        assert execution is not None
        assert execution.action_type == "generateMitigationPlan"
        assert execution.actor_id == "planner-user-1"
        assert execution.invocation_mode == "direct"
        assert execution.parent_execution_id is None
        assert execution.status == "failed"
        assert execution.error_code == "RISK_EVENT_NOT_FOUND"
        assert execution.error_message == "Risk event 'RISK-DOES-NOT-EXIST' was not found."
        assert execution.completed_at is not None


def test_approve_mitigation_plan_route_persists_child_action_execution(database_client) -> None:
    generate_request_id = "exec-generate-parent-approval-001"
    approve_request_id = "exec-approve-001"

    override = _use_actor(database_client, _planner_actor())
    next(override)
    try:
        generate_response = database_client.post(
            "/api/v1/actions/generateMitigationPlan",
            headers={REQUEST_ID_HEADER: generate_request_id},
            json={"parameters": {"riskEventId": "RISK-102"}},
        )
    finally:
        try:
            next(override)
        except StopIteration:
            pass

    assert generate_response.status_code == 200
    mitigation_plan_id = generate_response.json()["data"]["result"]["mitigationPlanId"]

    override = _use_actor(database_client, _operations_manager_actor())
    next(override)
    try:
        approve_response = database_client.post(
            "/api/v1/actions/approveMitigationPlan",
            headers={REQUEST_ID_HEADER: approve_request_id},
            json={"parameters": {"mitigationPlanId": mitigation_plan_id, "reason": "Approved for execution"}},
        )
    finally:
        try:
            next(override)
        except StopIteration:
            pass

    assert approve_response.status_code == 200

    with get_session_factory()() as session:
        repository = ActionExecutionRepository(session)
        parent_execution = repository.get_by_execution_id(approve_request_id)
        assert parent_execution is not None
        assert parent_execution.action_type == "approveMitigationPlan"
        assert parent_execution.actor_id == "ops-manager-1"
        assert parent_execution.actor_role == "OperationsManager"
        assert parent_execution.invocation_mode == "direct"
        assert parent_execution.parent_execution_id is None
        assert parent_execution.status == "succeeded"

        child_page = repository.search_execution_summaries(
            filters=ActionExecutionListFilters(parent_execution_id=approve_request_id),
            limit=10,
            offset=0,
        )
        assert len(child_page.records) == 1
        child_execution = child_page.records[0]
        assert child_execution.action_type == "reallocateInventory"
        assert child_execution.actor_id == "ops-manager-1"
        assert child_execution.actor_role == "OperationsManager"
        assert child_execution.invocation_mode == "child_action"
        assert child_execution.parent_execution_id == approve_request_id
        assert child_execution.status == "succeeded"

        audit_logs = AuditRepository(session).get_by_execution_id(child_execution.execution_id)
        assert audit_logs
        assert {audit_log.action_type for audit_log in audit_logs} == {"reallocateInventory"}
