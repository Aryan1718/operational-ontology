"""Persist draft mitigation plans from read-only recommendations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import ApplicationError
from app.repositories.audit_repository import AuditRepository
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.models.risk import RiskEvent
from app.models.supply_chain import Part, PurchaseOrder, Shipment, Warehouse
from app.runtime.action_engine import ActionExecutionContext
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.actions import (
    GenerateMitigationPlanParameters,
    GenerateMitigationPlanResult,
)
from app.schemas.functions import RecommendMitigationPlanParameters

ZERO = Decimal("0.00")
ACTIVE_PLAN_STATUSES = frozenset({"draft", "proposed", "approved", "executing"})
ALLOWED_RISK_STATUSES = frozenset({"open", "investigating"})
ALLOWED_STEP_ACTIONS = {
    "reallocate_inventory": "reallocateInventory",
    "expedite_purchase_order": "expeditePurchaseOrder",
    "prioritize_shipment": "prioritizeShipment",
}
PERSISTABLE_STEP_ACTIONS = frozenset({"reallocate_inventory", "expedite_purchase_order"})
PLAN_TYPE_FALLBACK = "reallocate_inventory"


class RiskEventNotFoundError(ApplicationError):
    """Raised when the target risk event does not exist."""

    def __init__(self, risk_event_id: str) -> None:
        super().__init__(
            code="RISK_EVENT_NOT_FOUND",
            message=f"Risk event '{risk_event_id}' was not found.",
            status_code=404,
            details={"riskEventId": risk_event_id},
        )


class InvalidRiskEventStateError(ApplicationError):
    """Raised when the risk event cannot accept mitigation planning."""

    def __init__(self, risk_event_id: str, status: str) -> None:
        super().__init__(
            code="INVALID_RISK_EVENT_STATE",
            message="The risk event is not in a state that allows mitigation planning.",
            status_code=409,
            details={"riskEventId": risk_event_id, "status": status},
        )


class ActiveMitigationPlanConflictError(ApplicationError):
    """Raised when one active plan already exists for the risk event."""

    def __init__(self, risk_event_id: str, mitigation_plan_id: str) -> None:
        super().__init__(
            code="ACTIVE_MITIGATION_PLAN_EXISTS",
            message="An active mitigation plan already exists for this risk event.",
            status_code=409,
            details={
                "riskEventId": risk_event_id,
                "mitigationPlanId": mitigation_plan_id,
                "activeStatuses": sorted(ACTIVE_PLAN_STATUSES),
            },
        )


class NoFeasibleMitigationError(ApplicationError):
    """Raised when the recommendation produces no executable plan."""

    def __init__(self, risk_event_id: str) -> None:
        super().__init__(
            code="NO_FEASIBLE_MITIGATION",
            message="No feasible mitigation plan could be generated for this risk event.",
            status_code=409,
            details={"riskEventId": risk_event_id},
        )


class UnsupportedMitigationStepError(ApplicationError):
    """Raised when a recommendation step cannot be stored safely."""

    def __init__(self, step_type: str) -> None:
        super().__init__(
            code="UNSUPPORTED_MITIGATION_STEP",
            message="The recommendation contains a mitigation step that cannot be persisted safely.",
            status_code=409,
            details={"stepType": step_type},
        )


class InvalidMitigationStepError(ApplicationError):
    """Raised when a recommendation step payload is malformed."""

    def __init__(self, step_type: str, path: str) -> None:
        super().__init__(
            code="INVALID_MITIGATION_STEP",
            message="The recommendation contains an invalid mitigation step.",
            status_code=422,
            details={"stepType": step_type, "path": path},
        )


@dataclass(frozen=True, slots=True)
class TargetStepBindings:
    """Resolved step foreign keys for the persisted mitigation row."""

    source_warehouse_id: UUID | None = None
    target_warehouse_id: UUID | None = None
    purchase_order_id: UUID | None = None
    shipment_id: UUID | None = None
    part_id: UUID | None = None
    quantity: Decimal | None = None


def generate_mitigation_plan(
    context: ActionExecutionContext,
    parameters: GenerateMitigationPlanParameters,
) -> GenerateMitigationPlanResult:
    """Create one persisted draft plan and ordered draft steps."""
    risk_event = _load_risk_event_for_update(context, parameters.risk_event_id)
    _validate_risk_event_state(risk_event, parameters.risk_event_id)
    existing_plan = _find_active_plan(context, risk_event.id)
    if existing_plan is not None:
        raise ActiveMitigationPlanConflictError(
            parameters.risk_event_id,
            existing_plan.mitigation_code,
        )

    recommendation = _run_recommendation(context, parameters.risk_event_id)
    if (
        recommendation.recommended_strategy == "no_feasible_mitigation"
        or not recommendation.mitigation_steps
    ):
        raise NoFeasibleMitigationError(parameters.risk_event_id)

    now = context.executed_at
    plan = MitigationPlan(
        mitigation_code=_generate_mitigation_code(context),
        risk_event_id=risk_event.id,
        plan_type=PLAN_TYPE_FALLBACK,
        status="draft",
        recommended_action=recommendation.recommended_strategy,
        explanation=_build_plan_explanation_payload(
            recommendation=recommendation,
            parameters=parameters,
            generated_by=_resolve_generated_by(context),
            executed_at=now,
        ),
        estimated_cost=recommendation.estimated_cost,
        confidence_score=(recommendation.confidence_score * Decimal("100")).quantize(
            Decimal("0.01")
        ),
        created_by=_try_parse_uuid(context.actor.actor_id),
    )
    context.session.add(plan)
    context.session.flush()

    step_ids: list[str] = []
    persisted_step_types: list[str] = []
    for recommended_step in recommendation.mitigation_steps:
        _validate_step_contract(recommended_step.step_type, recommended_step.parameters)
        if recommended_step.step_type not in PERSISTABLE_STEP_ACTIONS:
            raise UnsupportedMitigationStepError(recommended_step.step_type)
        bindings = _resolve_step_bindings(context, recommended_step.parameters)
        step = MitigationPlanStep(
            mitigation_plan_id=plan.id,
            step_order=recommended_step.sequence_number,
            action_type=recommended_step.step_type,
            status="pending",
            source_warehouse_id=bindings.source_warehouse_id,
            target_warehouse_id=bindings.target_warehouse_id,
            purchase_order_id=bindings.purchase_order_id,
            shipment_id=bindings.shipment_id,
            part_id=bindings.part_id,
            quantity=bindings.quantity,
            notes=_build_step_notes_payload(recommended_step),
        )
        context.session.add(step)
        context.session.flush()
        step_ids.append(str(step.id))
        persisted_step_types.append(step.action_type)
        _record_step_audit(context, step, recommended_step)

    if persisted_step_types:
        plan.plan_type = persisted_step_types[0]

    _record_plan_audit(
        context=context,
        plan=plan,
        recommendation=recommendation,
        notes=parameters.notes,
    )

    return GenerateMitigationPlanResult(
        mitigationPlanId=plan.mitigation_code,
        riskEventId=parameters.risk_event_id,
        status="draft",
        strategy=recommendation.recommended_strategy,
        summary=recommendation.summary,
        confidenceScore=recommendation.confidence_score,
        estimatedCost=recommendation.estimated_cost,
        generatedBy=_resolve_generated_by(context),
        stepIds=step_ids,
        stepCount=len(step_ids),
        createdAt=now,
        warnings=recommendation.warnings,
    )


def _load_risk_event_for_update(
    context: ActionExecutionContext,
    risk_event_id: str,
) -> RiskEvent:
    statement = (
        select(RiskEvent)
        .where(RiskEvent.risk_code == risk_event_id)
        .with_for_update()
    )
    risk_event = context.session.execute(statement).scalar_one_or_none()
    if risk_event is None:
        raise RiskEventNotFoundError(risk_event_id)
    return risk_event


def _validate_risk_event_state(risk_event: RiskEvent, risk_event_id: str) -> None:
    if risk_event.status not in ALLOWED_RISK_STATUSES:
        raise InvalidRiskEventStateError(risk_event_id, risk_event.status)


def _find_active_plan(
    context: ActionExecutionContext,
    risk_event_db_id: UUID,
) -> MitigationPlan | None:
    statement = (
        select(MitigationPlan)
        .where(
            MitigationPlan.risk_event_id == risk_event_db_id,
            MitigationPlan.status.in_(tuple(ACTIVE_PLAN_STATUSES)),
        )
        .order_by(MitigationPlan.created_at.desc(), MitigationPlan.id.desc())
        .with_for_update()
    )
    return context.session.execute(statement).scalars().first()


def _run_recommendation(
    context: ActionExecutionContext,
    risk_event_id: str,
) -> Any:
    handler = context.function_handler_registry.require("recommendMitigationPlan")
    function_context = FunctionExecutionContext(
        session=context.session,
        registry=context.registry,
        request_id=context.request_id,
        executed_at=context.executed_at,
    )
    return handler.execute(
        function_context,
        RecommendMitigationPlanParameters(riskEventId=risk_event_id),
    )


def _generate_mitigation_code(context: ActionExecutionContext) -> str:
    statement = select(MitigationPlan.mitigation_code).order_by(MitigationPlan.created_at.asc())
    next_number = 1001
    for mitigation_code in context.session.execute(statement).scalars():
        if not mitigation_code.startswith("MIT-"):
            continue
        try:
            next_number = max(next_number, int(mitigation_code.split("-", 1)[1]) + 1)
        except ValueError:
            continue
    return f"MIT-{next_number}"


def _validate_step_contract(step_type: str, parameters: dict[str, Any]) -> None:
    action_name = ALLOWED_STEP_ACTIONS.get(step_type)
    if action_name is None:
        raise UnsupportedMitigationStepError(step_type)
    if step_type == "reallocate_inventory":
        required_fields = (
            "sourceWarehouseId",
            "destinationWarehouseId",
            "partId",
            "quantity",
        )
    elif step_type == "expedite_purchase_order":
        required_fields = (
            "purchaseOrderId",
            "partId",
            "quantity",
            "targetExpectedDate",
        )
    else:
        required_fields = ("shipmentId",)
    for field_name in required_fields:
        if field_name not in parameters:
            raise InvalidMitigationStepError(step_type, field_name)


def _resolve_step_bindings(
    context: ActionExecutionContext,
    parameters: dict[str, Any],
) -> TargetStepBindings:
    source_warehouse_id = None
    target_warehouse_id = None
    purchase_order_id = None
    shipment_id = None
    part_id = None
    quantity = None

    if "sourceWarehouseId" in parameters:
        source_warehouse_id = _lookup_code(
            context,
            Warehouse,
            Warehouse.warehouse_code,
            parameters["sourceWarehouseId"],
        )
    if "destinationWarehouseId" in parameters:
        target_warehouse_id = _lookup_code(
            context,
            Warehouse,
            Warehouse.warehouse_code,
            parameters["destinationWarehouseId"],
        )
    if "purchaseOrderId" in parameters:
        purchase_order_id = _lookup_code(
            context,
            PurchaseOrder,
            PurchaseOrder.purchase_order_code,
            parameters["purchaseOrderId"],
        )
    if "shipmentId" in parameters:
        shipment_id = _lookup_code(
            context,
            Shipment,
            Shipment.shipment_code,
            parameters["shipmentId"],
        )
    if "partId" in parameters:
        part_id = _lookup_code(context, Part, Part.part_code, parameters["partId"])
    if "quantity" in parameters:
        quantity = Decimal(str(parameters["quantity"]))
        if quantity <= ZERO:
            raise InvalidMitigationStepError("quantity", "quantity")

    return TargetStepBindings(
        source_warehouse_id=source_warehouse_id,
        target_warehouse_id=target_warehouse_id,
        purchase_order_id=purchase_order_id,
        shipment_id=shipment_id,
        part_id=part_id,
        quantity=quantity,
    )


def _lookup_code(context: ActionExecutionContext, model: Any, column: Any, code: Any) -> UUID:
    statement = select(model.id).where(column == str(code))
    resolved = context.session.execute(statement).scalar_one_or_none()
    if resolved is None:
        raise InvalidMitigationStepError(model.__name__, str(code))
    return resolved


def _build_plan_explanation_payload(
    *,
    recommendation: Any,
    parameters: GenerateMitigationPlanParameters,
    generated_by: str,
    executed_at: datetime,
) -> str:
    payload = {
        "summary": recommendation.summary,
        "explanation": recommendation.explanation,
        "projectedOrdersRecovered": recommendation.projected_orders_recovered,
        "projectedRevenueProtected": str(recommendation.projected_revenue_protected),
        "remainingAtRiskOrderIds": recommendation.remaining_at_risk_order_ids,
        "alternativeStrategies": [
            item.model_dump(mode="json", by_alias=True)
            for item in recommendation.alternative_strategies
        ],
        "assumptions": recommendation.assumptions,
        "warnings": recommendation.warnings,
        "evidence": recommendation.evidence.model_dump(mode="json", by_alias=True),
        "strategyPreference": parameters.strategy_preference,
        "notes": parameters.notes,
        "generatedBy": generated_by,
        "snapshotExecutedAt": executed_at.astimezone(UTC).isoformat(),
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _build_step_notes_payload(recommended_step: Any) -> str:
    payload = {
        "targetObjectType": recommended_step.target_object_type,
        "targetObjectId": recommended_step.target_object_id,
        "parameters": recommended_step.parameters,
        "estimatedCost": str(recommended_step.estimated_cost),
        "expectedBenefit": recommended_step.expected_benefit.model_dump(
            mode="json",
            by_alias=True,
        ),
        "evidence": recommended_step.evidence,
        "governedAction": ALLOWED_STEP_ACTIONS[recommended_step.step_type],
    }
    return json.dumps(payload, separators=(",", ":"), default=str)


def _record_plan_audit(
    *,
    context: ActionExecutionContext,
    plan: MitigationPlan,
    recommendation: Any,
    notes: str | None,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="generateMitigationPlan",
        object_type="mitigation_plan",
        object_id=plan.id,
        previous_value=None,
        new_value={
            "mitigationCode": plan.mitigation_code,
            "riskEventId": recommendation.risk_event_id,
            "status": "draft",
            "strategy": recommendation.recommended_strategy,
            "stepCount": len(recommendation.mitigation_steps),
        },
        reason=notes,
    )


def _record_step_audit(
    context: ActionExecutionContext,
    step: MitigationPlanStep,
    recommended_step: Any,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="generateMitigationPlan",
        object_type="mitigation_plan_step",
        object_id=step.id,
        previous_value=None,
        new_value={
            "sequenceNumber": recommended_step.sequence_number,
            "stepType": recommended_step.step_type,
            "targetObjectType": recommended_step.target_object_type,
            "targetObjectId": recommended_step.target_object_id,
        },
        reason=None,
    )


def _resolve_generated_by(context: ActionExecutionContext) -> str:
    if context.actor.actor_type.value == "ai_agent":
        return "ai_agent"
    if context.actor.actor_type.value == "service":
        return "system"
    return "user"


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
