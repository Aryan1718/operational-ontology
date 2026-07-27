"""Reallocate inventory between warehouses for one approved mitigation plan."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.orm import aliased

from app.core.exceptions import ApplicationError, ObjectNotFoundError
from app.models.audit_log import AuditLog
from app.models.mitigation import MitigationPlan, MitigationPlanStep
from app.models.supply_chain import Inventory, Part, Warehouse
from app.runtime.action_engine import ActionExecutionContext
from app.schemas.actions import (
    ReallocatedInventoryPosition,
    ReallocateInventoryParameters,
    ReallocateInventoryResult,
)

ZERO = Decimal("0")
EXECUTABLE_PLAN_STATUS = "approved"
STEP_EXECUTION_STATUSES = frozenset({"pending", "approved", "executing"})


class MitigationPlanNotApprovedError(ApplicationError):
    """Raised when a mitigation plan is not executable."""

    def __init__(self, mitigation_plan_id: str, status: str) -> None:
        super().__init__(
            code="MITIGATION_PLAN_NOT_APPROVED",
            message="The mitigation plan is not approved for execution.",
            status_code=409,
            details={
                "mitigationPlanId": mitigation_plan_id,
                "status": status,
                "requiredStatus": EXECUTABLE_PLAN_STATUS,
            },
        )


class InvalidTransferQuantityError(ApplicationError):
    """Raised when the transfer quantity is not greater than zero."""

    def __init__(self, quantity: Decimal) -> None:
        super().__init__(
            code="INVALID_TRANSFER_QUANTITY",
            message="The transfer quantity must be greater than zero.",
            status_code=422,
            details={"quantity": str(quantity)},
        )


class SameWarehouseTransferError(ApplicationError):
    """Raised when the source and destination warehouses are identical."""

    def __init__(self, warehouse_id: str) -> None:
        super().__init__(
            code="SAME_SOURCE_AND_DESTINATION_WAREHOUSE",
            message="The source and destination warehouses must be different.",
            status_code=422,
            details={"warehouseId": warehouse_id},
        )


class InventoryItemMismatchError(ApplicationError):
    """Raised when the loaded inventory rows do not match the requested part."""

    def __init__(self, part_id: str) -> None:
        super().__init__(
            code="MISMATCHED_INVENTORY_ITEM",
            message="The source and destination inventory must match the requested item.",
            status_code=409,
            details={"partId": part_id},
        )


class InsufficientInventoryError(ApplicationError):
    """Raised when the source warehouse lacks enough available inventory."""

    def __init__(
        self,
        warehouse_id: str,
        available_quantity: Decimal,
        requested_quantity: Decimal,
    ) -> None:
        super().__init__(
            code="INSUFFICIENT_SOURCE_INVENTORY",
            message="The source warehouse does not have enough available inventory.",
            status_code=409,
            details={
                "warehouseId": warehouse_id,
                "availableQuantity": str(available_quantity),
                "requestedQuantity": str(requested_quantity),
            },
        )


def reallocate_inventory(
    context: ActionExecutionContext,
    parameters: ReallocateInventoryParameters,
) -> ReallocateInventoryResult:
    """Move one approved part inventory quantity between two warehouses atomically."""
    if parameters.quantity <= ZERO:
        raise InvalidTransferQuantityError(parameters.quantity)
    if parameters.source_warehouse_id == parameters.destination_warehouse_id:
        raise SameWarehouseTransferError(parameters.source_warehouse_id)

    plan = _load_mitigation_plan_for_update(context, parameters.mitigation_plan_id)
    if plan.status != EXECUTABLE_PLAN_STATUS:
        raise MitigationPlanNotApprovedError(parameters.mitigation_plan_id, plan.status)

    source_inventory, destination_inventory = _load_inventory_pair_for_update(context, parameters)
    _validate_inventory_pair(source_inventory, destination_inventory, parameters)

    previous_source_quantity = source_inventory.on_hand_quantity
    previous_destination_quantity = destination_inventory.on_hand_quantity
    available_quantity = source_inventory.on_hand_quantity - source_inventory.reserved_quantity
    if available_quantity < parameters.quantity:
        raise InsufficientInventoryError(
            parameters.source_warehouse_id,
            available_quantity,
            parameters.quantity,
        )

    new_source_quantity = source_inventory.on_hand_quantity - parameters.quantity
    if new_source_quantity < ZERO:
        raise InsufficientInventoryError(
            parameters.source_warehouse_id,
            available_quantity,
            parameters.quantity,
        )

    source_inventory.on_hand_quantity = new_source_quantity
    destination_inventory.on_hand_quantity = destination_inventory.on_hand_quantity + parameters.quantity

    _mark_matching_reallocation_step_executed(
        context=context,
        mitigation_plan_db_id=plan.id,
        parameters=parameters,
    )
    context.session.flush()

    _record_inventory_audit(
        context=context,
        inventory=source_inventory,
        warehouse_id=parameters.source_warehouse_id,
        part_id=parameters.part_id,
        previous_quantity=previous_source_quantity,
        new_quantity=source_inventory.on_hand_quantity,
        parameters=parameters,
    )
    _record_inventory_audit(
        context=context,
        inventory=destination_inventory,
        warehouse_id=parameters.destination_warehouse_id,
        part_id=parameters.part_id,
        previous_quantity=previous_destination_quantity,
        new_quantity=destination_inventory.on_hand_quantity,
        parameters=parameters,
    )

    return ReallocateInventoryResult(
        mitigationPlanId=parameters.mitigation_plan_id,
        partId=parameters.part_id,
        transferQuantity=parameters.quantity,
        sourceWarehouseId=parameters.source_warehouse_id,
        destinationWarehouseId=parameters.destination_warehouse_id,
        sourceInventory=_build_result_position(
            source_inventory,
            parameters.source_warehouse_id,
            parameters.part_id,
        ),
        destinationInventory=_build_result_position(
            destination_inventory,
            parameters.destination_warehouse_id,
            parameters.part_id,
        ),
        warnings=[],
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


def _load_inventory_pair_for_update(
    context: ActionExecutionContext,
    parameters: ReallocateInventoryParameters,
) -> tuple[Inventory, Inventory]:
    ordering = case(
        (Warehouse.warehouse_code == parameters.source_warehouse_id, 0),
        (Warehouse.warehouse_code == parameters.destination_warehouse_id, 1),
        else_=2,
    )
    statement = (
        select(Inventory, Warehouse.warehouse_code)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .join(Part, Part.id == Inventory.part_id)
        .where(
            Inventory.item_type == "part",
            Warehouse.warehouse_code.in_(
                (parameters.source_warehouse_id, parameters.destination_warehouse_id)
            ),
            Part.part_code == parameters.part_id,
        )
        .order_by(ordering, Warehouse.warehouse_code.asc(), Inventory.id.asc())
        .with_for_update()
    )

    source_inventory = None
    destination_inventory = None
    for inventory, warehouse_code in context.session.execute(statement).all():
        if warehouse_code == parameters.source_warehouse_id:
            source_inventory = inventory
        elif warehouse_code == parameters.destination_warehouse_id:
            destination_inventory = inventory

    if source_inventory is None:
        raise ObjectNotFoundError(
            "InventoryPosition",
            f"{parameters.source_warehouse_id}:{parameters.part_id}",
        )
    if destination_inventory is None:
        raise ObjectNotFoundError(
            "InventoryPosition",
            f"{parameters.destination_warehouse_id}:{parameters.part_id}",
        )
    return source_inventory, destination_inventory


def _validate_inventory_pair(
    source_inventory: Inventory,
    destination_inventory: Inventory,
    parameters: ReallocateInventoryParameters,
) -> None:
    if (
        source_inventory.item_type != "part"
        or destination_inventory.item_type != "part"
        or source_inventory.part_id is None
        or destination_inventory.part_id is None
        or source_inventory.part_id != destination_inventory.part_id
    ):
        raise InventoryItemMismatchError(parameters.part_id)


def _mark_matching_reallocation_step_executed(
    *,
    context: ActionExecutionContext,
    mitigation_plan_db_id: UUID,
    parameters: ReallocateInventoryParameters,
) -> None:
    source_warehouse = aliased(Warehouse)
    destination_warehouse = aliased(Warehouse)
    statement = (
        select(MitigationPlanStep)
        .join(
            source_warehouse,
            source_warehouse.id == MitigationPlanStep.source_warehouse_id,
        )
        .join(
            destination_warehouse,
            destination_warehouse.id == MitigationPlanStep.target_warehouse_id,
        )
        .join(Part, Part.id == MitigationPlanStep.part_id)
        .where(
            MitigationPlanStep.mitigation_plan_id == mitigation_plan_db_id,
            MitigationPlanStep.action_type == "reallocate_inventory",
            MitigationPlanStep.status.in_(tuple(STEP_EXECUTION_STATUSES)),
            source_warehouse.warehouse_code == parameters.source_warehouse_id,
            destination_warehouse.warehouse_code == parameters.destination_warehouse_id,
            Part.part_code == parameters.part_id,
            MitigationPlanStep.quantity == parameters.quantity,
        )
        .order_by(MitigationPlanStep.step_order.asc(), MitigationPlanStep.id.asc())
        .with_for_update()
    )
    step = context.session.execute(statement).scalars().first()
    if step is None:
        return
    step.status = "executed"
    step.executed_at = context.executed_at


def _record_inventory_audit(
    *,
    context: ActionExecutionContext,
    inventory: Inventory,
    warehouse_id: str,
    part_id: str,
    previous_quantity: Decimal,
    new_quantity: Decimal,
    parameters: ReallocateInventoryParameters,
) -> None:
    context.session.add(
        AuditLog(
            actor_user_id=_try_parse_uuid(context.actor.actor_id),
            action_type="reallocateInventory",
            object_type="inventory",
            object_id=inventory.id,
            previous_value=_build_audit_state(
                context=context,
                inventory=inventory,
                warehouse_id=warehouse_id,
                part_id=part_id,
                previous_quantity=previous_quantity,
                new_quantity=new_quantity,
                parameters=parameters,
            ),
            new_value=_build_audit_state(
                context=context,
                inventory=inventory,
                warehouse_id=warehouse_id,
                part_id=part_id,
                previous_quantity=previous_quantity,
                new_quantity=new_quantity,
                parameters=parameters,
            ),
            reason=parameters.reason,
            created_at=context.executed_at,
        )
    )


def _build_audit_state(
    *,
    context: ActionExecutionContext,
    inventory: Inventory,
    warehouse_id: str,
    part_id: str,
    previous_quantity: Decimal,
    new_quantity: Decimal,
    parameters: ReallocateInventoryParameters,
) -> dict[str, object]:
    return {
        "actor": context.actor.actor_id,
        "actionType": "reallocateInventory",
        "objectId": str(inventory.id),
        "inventoryPositionId": str(inventory.id),
        "warehouseId": warehouse_id,
        "partId": part_id,
        "previousQuantity": str(previous_quantity),
        "newQuantity": str(new_quantity),
        "transferQuantity": str(parameters.quantity),
        "sourceWarehouse": parameters.source_warehouse_id,
        "destinationWarehouse": parameters.destination_warehouse_id,
        "mitigationPlanId": parameters.mitigation_plan_id,
        "reason": parameters.reason,
        "onHandQuantity": str(new_quantity),
        "reservedQuantity": str(inventory.reserved_quantity),
        "availableQuantity": str(new_quantity - inventory.reserved_quantity),
    }


def _build_result_position(
    inventory: Inventory,
    warehouse_id: str,
    part_id: str,
) -> ReallocatedInventoryPosition:
    return ReallocatedInventoryPosition(
        inventoryPositionId=str(inventory.id),
        warehouseId=warehouse_id,
        partId=part_id,
        onHandQuantity=inventory.on_hand_quantity,
        reservedQuantity=inventory.reserved_quantity,
        availableQuantity=inventory.on_hand_quantity - inventory.reserved_quantity,
    )


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
