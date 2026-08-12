"""Expedite one purchase order as a trusted mitigation child action."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select

from app.core.exceptions import ApplicationError, ObjectNotFoundError
from app.repositories.audit_repository import AuditRepository
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.models.supply_chain import Part, PurchaseOrder, PurchaseOrderItem
from app.runtime.action_engine import ActionExecutionContext
from app.schemas.actions import ExpeditePurchaseOrderParameters, ExpeditePurchaseOrderResult

ZERO = Decimal("0.00")
CHILD_INVOCATION_MODE = "child"
REQUIRED_PARENT_ACTION = "executeMitigationPlan"
EXECUTING_PLAN_STATUS = "executing"
PENDING_STEP_STATUS = "pending"
EXECUTED_STEP_STATUS = "executed"
ELIGIBLE_PURCHASE_ORDER_STATUSES = frozenset({"open"})
STEP_ACTION_TYPE = "expedite_purchase_order"
STEP_NOTES_PARAMETERS_KEY = "parameters"
STEP_NOTES_ESTIMATED_COST_KEY = "estimatedCost"
STEP_NOTES_TARGET_EXPECTED_DATE_KEY = "targetExpectedDate"
STEP_NOTES_PURCHASE_ORDER_ID_KEY = "purchaseOrderId"
STEP_NOTES_PART_ID_KEY = "partId"


class ChildActionInvocationRequiredError(ApplicationError):
    """Raised when expeditePurchaseOrder is not invoked from the trusted parent action."""

    def __init__(self, context: ActionExecutionContext) -> None:
        super().__init__(
            code="OPERATION_NOT_PERMITTED",
            message="This action may only execute as a trusted child action.",
            status_code=403,
            details={
                "requiredInvocationMode": CHILD_INVOCATION_MODE,
                "requiredParentActionName": REQUIRED_PARENT_ACTION,
                "invocationMode": context.invocation_mode,
                "parentActionName": context.parent_action_name,
                "parentExecutionId": context.parent_execution_id,
            },
        )


class InvalidMitigationPlanExecutionStateError(ApplicationError):
    """Raised when the mitigation plan is not currently executing."""

    def __init__(self, mitigation_plan_id: str, status: str) -> None:
        super().__init__(
            code="INVALID_MITIGATION_PLAN_STATE",
            message="The mitigation plan is not currently executing.",
            status_code=409,
            details={
                "mitigationPlanId": mitigation_plan_id,
                "status": status,
                "requiredStatus": EXECUTING_PLAN_STATUS,
            },
        )


class FrozenMitigationStepMismatchError(ApplicationError):
    """Raised when no pending mitigation step matches the trusted frozen payload."""

    def __init__(self, mitigation_plan_id: str, purchase_order_id: str) -> None:
        super().__init__(
            code="INVALID_MITIGATION_STEP",
            message="The mitigation step payload does not match the requested expedite action.",
            status_code=409,
            details={
                "mitigationPlanId": mitigation_plan_id,
                "purchaseOrderId": purchase_order_id,
                "requiredActionType": STEP_ACTION_TYPE,
            },
        )


class InvalidMitigationStepStateError(ApplicationError):
    """Raised when the matched mitigation step is not still pending."""

    def __init__(self, mitigation_step_id: str, status: str) -> None:
        super().__init__(
            code="INVALID_MITIGATION_STEP_STATE",
            message="The mitigation step is not pending execution.",
            status_code=409,
            details={
                "mitigationStepId": mitigation_step_id,
                "status": status,
                "requiredStatus": PENDING_STEP_STATUS,
            },
        )


class InvalidPurchaseOrderStateError(ApplicationError):
    """Raised when a purchase order cannot be expedited in its current state."""

    def __init__(self, purchase_order_id: str, status: str) -> None:
        super().__init__(
            code="INVALID_PURCHASE_ORDER_STATE",
            message="The purchase order is not eligible for expediting.",
            status_code=409,
            details={
                "purchaseOrderId": purchase_order_id,
                "status": status,
                "allowedStatuses": sorted(ELIGIBLE_PURCHASE_ORDER_STATUSES),
            },
        )


class PurchaseOrderAlreadyExpeditedError(ApplicationError):
    """Raised when a purchase order has already been expedited."""

    def __init__(self, purchase_order_id: str) -> None:
        super().__init__(
            code="PURCHASE_ORDER_ALREADY_EXPEDITED",
            message="The purchase order has already been expedited.",
            status_code=409,
            details={"purchaseOrderId": purchase_order_id},
        )


class InvalidExpectedDeliveryDateError(ApplicationError):
    """Raised when the requested expedited delivery date is invalid."""

    def __init__(
        self,
        purchase_order_id: str,
        *,
        current_expected_delivery_date: date | None,
        requested_expected_delivery_date: date,
        executed_on: date,
    ) -> None:
        super().__init__(
            code="INVALID_EXPECTED_DELIVERY_DATE",
            message="The expedited delivery date is invalid.",
            status_code=422,
            details={
                "purchaseOrderId": purchase_order_id,
                "currentExpectedDeliveryDate": (
                    current_expected_delivery_date.isoformat()
                    if current_expected_delivery_date is not None
                    else None
                ),
                "requestedExpectedDeliveryDate": requested_expected_delivery_date.isoformat(),
                "executedOn": executed_on.isoformat(),
            },
        )


class InvalidAdditionalCostError(ApplicationError):
    """Raised when the requested additional expedite cost is invalid."""

    def __init__(self, purchase_order_id: str, additional_cost: Decimal) -> None:
        super().__init__(
            code="INVALID_ADDITIONAL_COST",
            message="The additional expedite cost must be greater than or equal to zero.",
            status_code=422,
            details={
                "purchaseOrderId": purchase_order_id,
                "additionalCost": str(additional_cost),
            },
        )


class NoOpenPurchaseOrderQuantityError(ApplicationError):
    """Raised when the purchase order has no remaining open quantity."""

    def __init__(self, purchase_order_id: str) -> None:
        super().__init__(
            code="PURCHASE_ORDER_HAS_NO_OPEN_QUANTITY",
            message="The purchase order has no open quantity available to expedite.",
            status_code=409,
            details={"purchaseOrderId": purchase_order_id},
        )


class PurchaseOrderPartNotOpenError(ApplicationError):
    """Raised when the targeted part has no open line on the purchase order."""

    def __init__(self, purchase_order_id: str, part_id: str) -> None:
        super().__init__(
            code="PURCHASE_ORDER_PART_NOT_OPEN",
            message="The purchase order does not contain an open line for the targeted part.",
            status_code=409,
            details={
                "purchaseOrderId": purchase_order_id,
                "partId": part_id,
            },
        )


def expedite_purchase_order(
    context: ActionExecutionContext,
    parameters: ExpeditePurchaseOrderParameters,
) -> ExpeditePurchaseOrderResult:
    """Expedite one eligible purchase order under a trusted executing mitigation plan."""
    _validate_child_action_context(context)
    if parameters.additional_cost < ZERO:
        raise InvalidAdditionalCostError(
            parameters.purchase_order_id,
            parameters.additional_cost,
        )

    purchase_order = _load_purchase_order_for_update(context, parameters.purchase_order_id)
    mitigation_plan = _load_mitigation_plan_for_update(context, parameters.mitigation_plan_id)
    if mitigation_plan.status != EXECUTING_PLAN_STATUS:
        raise InvalidMitigationPlanExecutionStateError(
            parameters.mitigation_plan_id,
            mitigation_plan.status,
        )

    if purchase_order.status not in ELIGIBLE_PURCHASE_ORDER_STATUSES:
        raise InvalidPurchaseOrderStateError(
            parameters.purchase_order_id,
            purchase_order.status,
        )
    if purchase_order.expedited:
        raise PurchaseOrderAlreadyExpeditedError(parameters.purchase_order_id)

    previous_expected_delivery_date = purchase_order.expected_delivery_date
    previous_expedite_cost = purchase_order.expedite_cost
    executed_on = context.executed_at.date()
    if (
        previous_expected_delivery_date is None
        or parameters.new_expected_delivery_date >= previous_expected_delivery_date
        or parameters.new_expected_delivery_date < executed_on
    ):
        raise InvalidExpectedDeliveryDateError(
            parameters.purchase_order_id,
            current_expected_delivery_date=previous_expected_delivery_date,
            requested_expected_delivery_date=parameters.new_expected_delivery_date,
            executed_on=executed_on,
        )

    line_items = _load_purchase_order_items_for_update(context, purchase_order.id)
    if _calculate_open_quantity(line_items) <= ZERO:
        raise NoOpenPurchaseOrderQuantityError(parameters.purchase_order_id)

    mitigation_step = _select_matching_mitigation_step(
        context=context,
        mitigation_plan=mitigation_plan,
        purchase_order=purchase_order,
        parameters=parameters,
    )
    if mitigation_step.status != PENDING_STEP_STATUS:
        raise InvalidMitigationStepStateError(str(mitigation_step.id), mitigation_step.status)

    notes_payload = _parse_step_notes_payload(
        mitigation_step=mitigation_step,
        mitigation_plan_id=parameters.mitigation_plan_id,
        purchase_order_id=parameters.purchase_order_id,
    )
    targeted_part_id = _extract_matching_frozen_values(
        notes_payload=notes_payload,
        parameters=parameters,
        mitigation_plan_id=parameters.mitigation_plan_id,
        purchase_order_id=parameters.purchase_order_id,
    )
    if targeted_part_id is not None and not _has_open_line_for_part(line_items, targeted_part_id):
        raise PurchaseOrderPartNotOpenError(parameters.purchase_order_id, targeted_part_id)

    purchase_order.expected_delivery_date = parameters.new_expected_delivery_date
    purchase_order.expedited = True
    purchase_order.expedite_cost = parameters.additional_cost
    purchase_order.updated_at = context.executed_at
    mitigation_step.status = EXECUTED_STEP_STATUS
    mitigation_step.executed_at = context.executed_at

    context.session.flush()

    _record_purchase_order_audit(
        context=context,
        purchase_order=purchase_order,
        mitigation_plan=mitigation_plan,
        previous_expected_delivery_date=previous_expected_delivery_date,
        previous_expedited=False,
        previous_expedite_cost=previous_expedite_cost,
        reason=parameters.reason,
    )
    _record_mitigation_step_audit(
        context=context,
        mitigation_plan=mitigation_plan,
        mitigation_step=mitigation_step,
        purchase_order_id=parameters.purchase_order_id,
        reason=parameters.reason,
    )

    return ExpeditePurchaseOrderResult(
        purchaseOrderId=parameters.purchase_order_id,
        mitigationPlanId=mitigation_plan.mitigation_code,
        mitigationStepId=str(mitigation_step.id),
        previousExpectedDeliveryDate=previous_expected_delivery_date,
        newExpectedDeliveryDate=purchase_order.expected_delivery_date,
        additionalCost=parameters.additional_cost,
        expedited=purchase_order.expedited,
        warnings=[],
    )


def _validate_child_action_context(context: ActionExecutionContext) -> None:
    if (
        context.invocation_mode != CHILD_INVOCATION_MODE
        or context.parent_action_name != REQUIRED_PARENT_ACTION
        or not context.parent_execution_id
    ):
        raise ChildActionInvocationRequiredError(context)


def _load_purchase_order_for_update(
    context: ActionExecutionContext,
    purchase_order_id: str,
) -> PurchaseOrder:
    statement = (
        select(PurchaseOrder)
        .where(PurchaseOrder.purchase_order_code == purchase_order_id)
        .with_for_update()
    )
    purchase_order = context.session.execute(statement).scalar_one_or_none()
    if purchase_order is None:
        raise ObjectNotFoundError("PurchaseOrder", purchase_order_id)
    return purchase_order


def _load_mitigation_plan_for_update(
    context: ActionExecutionContext,
    mitigation_plan_id: str,
) -> MitigationPlan:
    statement = (
        select(MitigationPlan)
        .where(MitigationPlan.mitigation_code == mitigation_plan_id)
        .with_for_update()
    )
    mitigation_plan = context.session.execute(statement).scalar_one_or_none()
    if mitigation_plan is None:
        raise ObjectNotFoundError("MitigationPlan", mitigation_plan_id)
    return mitigation_plan


def _load_purchase_order_items_for_update(
    context: ActionExecutionContext,
    purchase_order_db_id: UUID,
) -> list[PurchaseOrderItem]:
    statement = (
        select(PurchaseOrderItem)
        .where(PurchaseOrderItem.purchase_order_id == purchase_order_db_id)
        .order_by(PurchaseOrderItem.id.asc())
        .with_for_update()
    )
    return list(context.session.execute(statement).scalars())


def _select_matching_mitigation_step(
    *,
    context: ActionExecutionContext,
    mitigation_plan: MitigationPlan,
    purchase_order: PurchaseOrder,
    parameters: ExpeditePurchaseOrderParameters,
) -> MitigationPlanStep:
    statement = (
        select(MitigationPlanStep)
        .where(
            MitigationPlanStep.mitigation_plan_id == mitigation_plan.id,
            MitigationPlanStep.action_type == STEP_ACTION_TYPE,
            MitigationPlanStep.purchase_order_id == purchase_order.id,
        )
        .order_by(MitigationPlanStep.step_order.asc(), MitigationPlanStep.id.asc())
        .with_for_update()
    )
    candidates = list(context.session.execute(statement).scalars())
    if not candidates:
        raise ObjectNotFoundError(
            "MitigationPlanStep",
            f"{parameters.mitigation_plan_id}:{parameters.purchase_order_id}:{STEP_ACTION_TYPE}",
        )
    for candidate in candidates:
        payload = _parse_step_notes_payload(
            mitigation_step=candidate,
            mitigation_plan_id=parameters.mitigation_plan_id,
            purchase_order_id=parameters.purchase_order_id,
        )
        try:
            _extract_matching_frozen_values(
                notes_payload=payload,
                parameters=parameters,
                mitigation_plan_id=parameters.mitigation_plan_id,
                purchase_order_id=parameters.purchase_order_id,
            )
            return candidate
        except FrozenMitigationStepMismatchError:
            continue
    raise FrozenMitigationStepMismatchError(
        parameters.mitigation_plan_id,
        parameters.purchase_order_id,
    )


def _parse_step_notes_payload(
    *,
    mitigation_step: MitigationPlanStep,
    mitigation_plan_id: str,
    purchase_order_id: str,
) -> dict[str, object]:
    if mitigation_step.notes is None:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    try:
        parsed = json.loads(mitigation_step.notes)
    except json.JSONDecodeError as exc:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id) from exc
    if not isinstance(parsed, dict):
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    return parsed


def _extract_matching_frozen_values(
    *,
    notes_payload: dict[str, object],
    parameters: ExpeditePurchaseOrderParameters,
    mitigation_plan_id: str,
    purchase_order_id: str,
) -> str | None:
    frozen_parameters = notes_payload.get(STEP_NOTES_PARAMETERS_KEY)
    if not isinstance(frozen_parameters, dict):
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    frozen_purchase_order_id = frozen_parameters.get(STEP_NOTES_PURCHASE_ORDER_ID_KEY)
    frozen_expected_delivery_date = frozen_parameters.get(STEP_NOTES_TARGET_EXPECTED_DATE_KEY)
    frozen_estimated_cost = notes_payload.get(STEP_NOTES_ESTIMATED_COST_KEY)
    if frozen_purchase_order_id != parameters.purchase_order_id:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    try:
        parsed_expected_delivery_date = _coerce_date(frozen_expected_delivery_date)
        parsed_estimated_cost = _coerce_decimal(frozen_estimated_cost)
    except ValueError as exc:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id) from exc
    if parsed_expected_delivery_date != parameters.new_expected_delivery_date:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    if parsed_estimated_cost != parameters.additional_cost:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    frozen_part_id = frozen_parameters.get(STEP_NOTES_PART_ID_KEY)
    if frozen_part_id is None:
        return None
    if not isinstance(frozen_part_id, str) or not frozen_part_id:
        raise FrozenMitigationStepMismatchError(mitigation_plan_id, purchase_order_id)
    return frozen_part_id


def _coerce_date(raw_value: object) -> date:
    if not isinstance(raw_value, str):
        raise ValueError("Expected ISO date string.")
    return date.fromisoformat(raw_value)


def _coerce_decimal(raw_value: object) -> Decimal:
    try:
        return Decimal(str(raw_value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Expected decimal-compatible value.") from exc


def _calculate_open_quantity(line_items: list[PurchaseOrderItem]) -> Decimal:
    total = ZERO
    for line_item in line_items:
        total += line_item.quantity_ordered - line_item.quantity_received
    return total


def _has_open_line_for_part(line_items: list[PurchaseOrderItem], part_id: str) -> bool:
    for line_item in line_items:
        if line_item.part is not None and line_item.part.part_code == part_id:
            if line_item.quantity_ordered - line_item.quantity_received > ZERO:
                return True
    return False


def _record_purchase_order_audit(
    *,
    context: ActionExecutionContext,
    purchase_order: PurchaseOrder,
    mitigation_plan: MitigationPlan,
    previous_expected_delivery_date: date,
    previous_expedited: bool,
    previous_expedite_cost: Decimal | None,
    reason: str,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="expeditePurchaseOrder",
        object_type="purchase_order",
        object_id=purchase_order.id,
        previous_value={
            "purchaseOrderId": purchase_order.purchase_order_code,
            "expectedDeliveryDate": previous_expected_delivery_date.isoformat(),
            "expedited": previous_expedited,
            "expediteCost": (
                str(previous_expedite_cost) if previous_expedite_cost is not None else None
            ),
        },
        new_value={
            "purchaseOrderId": purchase_order.purchase_order_code,
            "mitigationPlanId": mitigation_plan.mitigation_code,
            "expectedDeliveryDate": purchase_order.expected_delivery_date.isoformat(),
            "expedited": purchase_order.expedited,
            "expediteCost": (
                str(purchase_order.expedite_cost)
                if purchase_order.expedite_cost is not None
                else None
            ),
        },
        reason=reason,
    )


def _record_mitigation_step_audit(
    *,
    context: ActionExecutionContext,
    mitigation_plan: MitigationPlan,
    mitigation_step: MitigationPlanStep,
    purchase_order_id: str,
    reason: str,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="expeditePurchaseOrder",
        object_type="mitigation_plan_step",
        object_id=mitigation_step.id,
        previous_value={
            "mitigationPlanId": mitigation_plan.mitigation_code,
            "mitigationStepId": str(mitigation_step.id),
            "purchaseOrderId": purchase_order_id,
            "status": PENDING_STEP_STATUS,
            "executedAt": None,
        },
        new_value={
            "mitigationPlanId": mitigation_plan.mitigation_code,
            "mitigationStepId": str(mitigation_step.id),
            "purchaseOrderId": purchase_order_id,
            "status": mitigation_step.status,
            "executedAt": mitigation_step.executed_at.isoformat(),
        },
        reason=reason,
    )


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
