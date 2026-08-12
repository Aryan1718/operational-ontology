"""Approve persisted mitigation plans and execute supported trusted child actions."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import ApplicationError, ObjectNotFoundError
from app.repositories.audit_repository import AuditRepository
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.runtime.action_engine import ActionExecutionContext
from app.schemas.actions import (
    ApproveMitigationPlanParameters,
    ApproveMitigationPlanResult,
)

AWAITING_APPROVAL_STATUSES = frozenset({"draft", "proposed"})
APPROVED_STATUS = "approved"
REALLOCATE_STEP_TYPE = "reallocate_inventory"
REALLOCATE_ACTION_NAME = "reallocateInventory"
EXECUTED_STEP_STATUS = "executed"
STEP_NOTES_PARAMETERS_KEY = "parameters"


class InvalidMitigationPlanApprovalStateError(ApplicationError):
    """Raised when a mitigation plan is no longer awaiting approval."""

    def __init__(self, mitigation_plan_id: str, status: str) -> None:
        super().__init__(
            code="INVALID_MITIGATION_PLAN_STATE",
            message="The mitigation plan is not awaiting approval.",
            status_code=409,
            details={
                "mitigationPlanId": mitigation_plan_id,
                "status": status,
                "allowedStatuses": sorted(AWAITING_APPROVAL_STATUSES),
            },
        )


def approve_mitigation_plan(
    context: ActionExecutionContext,
    parameters: ApproveMitigationPlanParameters,
) -> ApproveMitigationPlanResult:
    """Approve one generated mitigation plan and record the state transition."""
    plan = _load_mitigation_plan_for_update(context, parameters.mitigation_plan_id)
    previous_state = _serialize_plan_state(plan)
    previous_status = plan.status
    if previous_status not in AWAITING_APPROVAL_STATUSES:
        raise InvalidMitigationPlanApprovalStateError(
            parameters.mitigation_plan_id,
            previous_status,
        )

    actor_user_id = _try_parse_uuid(context.actor.actor_id)
    plan.status = APPROVED_STATUS
    plan.approved_by = actor_user_id
    plan.approved_at = context.executed_at

    reallocation_step = _load_reallocate_step_for_update(context, plan.id)

    context.session.flush()

    if _is_reallocate_recommendation(plan, reallocation_step):
        child_parameters = _build_reallocate_child_parameters(
            plan=plan,
            step=reallocation_step,
            approval_reason=parameters.reason,
        )
        context.execute_child_action(REALLOCATE_ACTION_NAME, child_parameters)
        if reallocation_step is not None:
            reallocation_step.status = EXECUTED_STEP_STATUS
            reallocation_step.executed_at = context.executed_at
            context.session.flush()

    _record_plan_audit(
        context=context,
        plan=plan,
        previous_state=previous_state,
        reason=parameters.reason,
    )

    return ApproveMitigationPlanResult(
        mitigationPlanId=plan.mitigation_code,
        previousStatus=previous_status,
        newStatus=plan.status,
        approvedBy=context.actor.actor_id,
        approvedAt=plan.approved_at,
        approvedEstimatedCost=plan.estimated_cost,
    )


def _load_reallocate_step_for_update(
    context: ActionExecutionContext,
    mitigation_plan_db_id,
) -> MitigationPlanStep | None:
    statement = (
        select(MitigationPlanStep)
        .where(
            MitigationPlanStep.mitigation_plan_id == mitigation_plan_db_id,
            MitigationPlanStep.action_type == REALLOCATE_STEP_TYPE,
        )
        .order_by(MitigationPlanStep.step_order.asc(), MitigationPlanStep.id.asc())
        .with_for_update()
    )
    return context.session.execute(statement).scalars().first()


def _is_reallocate_recommendation(
    plan: MitigationPlan,
    step: MitigationPlanStep | None,
) -> bool:
    return plan.plan_type == REALLOCATE_STEP_TYPE or (
        step is not None and step.action_type == REALLOCATE_STEP_TYPE
    )


def _build_reallocate_child_parameters(
    *,
    plan: MitigationPlan,
    step: MitigationPlanStep | None,
    approval_reason: str,
) -> dict[str, object]:
    raw_parameters: dict[str, object] = {
        "mitigationPlanId": plan.mitigation_code,
        "reason": approval_reason,
    }
    if step is None or step.notes is None:
        return raw_parameters
    try:
        payload = json.loads(step.notes)
    except json.JSONDecodeError:
        return raw_parameters
    if not isinstance(payload, dict):
        return raw_parameters
    frozen_parameters = payload.get(STEP_NOTES_PARAMETERS_KEY)
    if not isinstance(frozen_parameters, dict):
        return raw_parameters

    field_mapping = {
        "sourceWarehouseId": "fromWarehouseId",
        "destinationWarehouseId": "toWarehouseId",
        "partId": "partId",
        "quantity": "quantity",
    }
    for source_field, target_field in field_mapping.items():
        value = frozen_parameters.get(source_field)
        if value is not None:
            raw_parameters[target_field] = value
    return raw_parameters


def _load_mitigation_plan_for_update(
    context: ActionExecutionContext,
    mitigation_plan_id: str,
) -> MitigationPlan:
    statement = (
        select(MitigationPlan)
        .where(MitigationPlan.mitigation_code == mitigation_plan_id)
        .with_for_update()
    )
    plan = context.session.execute(statement).scalar_one_or_none()
    if plan is None:
        raise ObjectNotFoundError("MitigationPlan", mitigation_plan_id)
    return plan


def _serialize_plan_state(plan: MitigationPlan) -> dict[str, object | None]:
    return {
        "mitigationPlanId": plan.mitigation_code,
        "status": plan.status,
        "approvedBy": str(plan.approved_by) if plan.approved_by is not None else None,
        "approvedAt": plan.approved_at,
        "estimatedCost": plan.estimated_cost,
    }


def _record_plan_audit(
    *,
    context: ActionExecutionContext,
    plan: MitigationPlan,
    previous_state: dict[str, object | None],
    reason: str,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="approveMitigationPlan",
        object_type="mitigation_plan",
        object_id=plan.id,
        previous_value=previous_state,
        new_value=_serialize_plan_state(plan),
        reason=reason,
    )


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
