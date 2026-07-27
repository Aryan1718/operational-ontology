"""Approve persisted mitigation plans without executing operational changes."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import ApplicationError, ObjectNotFoundError
from app.models.audit_log import AuditLog
from app.models.mitigation import MitigationPlan
from app.runtime.action_engine import ActionExecutionContext
from app.schemas.actions import (
    ApproveMitigationPlanParameters,
    ApproveMitigationPlanResult,
)

AWAITING_APPROVAL_STATUSES = frozenset({"draft", "proposed"})
APPROVED_STATUS = "approved"
TERMINAL_OR_INELIGIBLE_STATUSES = frozenset(
    {"approved", "rejected", "cancelled", "executing", "executed"}
)


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
    context.session.add(
        AuditLog(
            actor_user_id=_try_parse_uuid(context.actor.actor_id),
            action_type="approveMitigationPlan",
            object_type="mitigation_plan",
            object_id=plan.id,
            previous_value=previous_state,
            new_value=_serialize_plan_state(plan),
            reason=reason,
            created_at=context.executed_at,
        )
    )


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
