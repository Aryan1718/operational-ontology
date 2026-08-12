"""Reallocate inventory between warehouses for one approved mitigation plan."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, select

from app.core.exceptions import ApplicationError, ObjectNotFoundError
from app.models.mitigation import MitigationPlan
from app.models.supply_chain import Inventory, Part, Warehouse
from app.repositories.audit_repository import AuditRepository
from app.runtime.action_engine import ActionExecutionContext
from app.schemas.actions import (
    ReallocatedInventoryPosition,
    ReallocateInventoryParameters,
    ReallocateInventoryResult,
)

ZERO = Decimal("0")
EXECUTABLE_PLAN_STATUS = "approved"


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
    """Raised when the source warehouse lacks enough transferable inventory."""

    def __init__(
        self,
        warehouse_id: str,
        transferable_quantity: Decimal,
        requested_quantity: Decimal,
    ) -> None:
        super().__init__(
            code="INSUFFICIENT_SOURCE_INVENTORY",
            message="The source warehouse does not have enough transferable inventory.",
            status_code=409,
            details={
                "warehouseId": warehouse_id,
                "transferableQuantity": str(transferable_quantity),
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
    if parameters.from_warehouse_id == parameters.to_warehouse_id:
        raise SameWarehouseTransferError(parameters.from_warehouse_id)

    plan = _load_mitigation_plan_for_update(context, parameters.mitigation_plan_id)
    if plan.status != EXECUTABLE_PLAN_STATUS:
        raise MitigationPlanNotApprovedError(parameters.mitigation_plan_id, plan.status)

    part = _load_part(context, parameters.part_id)
    source_warehouse = _load_warehouse(context, parameters.from_warehouse_id)
    destination_warehouse = _load_warehouse(context, parameters.to_warehouse_id)

    source_inventory, destination_inventory = _load_inventory_pair_for_update(
        context=context,
        part=part,
        source_warehouse=source_warehouse,
        destination_warehouse=destination_warehouse,
        parameters=parameters,
    )
    _validate_inventory_pair(source_inventory, destination_inventory, parameters)

    previous_source_quantity = source_inventory.on_hand_quantity
    previous_destination_quantity = destination_inventory.on_hand_quantity
    transferable_quantity = _calculate_transferable_quantity(source_inventory)
    if transferable_quantity < parameters.quantity:
        raise InsufficientInventoryError(
            parameters.from_warehouse_id,
            transferable_quantity,
            parameters.quantity,
        )

    source_inventory.on_hand_quantity = previous_source_quantity - parameters.quantity
    destination_inventory.on_hand_quantity = previous_destination_quantity + parameters.quantity

    context.session.flush()

    _record_inventory_audit(
        context=context,
        inventory=source_inventory,
        inventory_role="source",
        warehouse_id=parameters.from_warehouse_id,
        part_id=parameters.part_id,
        previous_quantity=previous_source_quantity,
        new_quantity=source_inventory.on_hand_quantity,
        counterpart_warehouse_id=parameters.to_warehouse_id,
        counterpart_previous_quantity=previous_destination_quantity,
        counterpart_new_quantity=destination_inventory.on_hand_quantity,
        mitigation_plan_id=plan.mitigation_code,
        parameters=parameters,
    )
    _record_inventory_audit(
        context=context,
        inventory=destination_inventory,
        inventory_role="destination",
        warehouse_id=parameters.to_warehouse_id,
        part_id=parameters.part_id,
        previous_quantity=previous_destination_quantity,
        new_quantity=destination_inventory.on_hand_quantity,
        counterpart_warehouse_id=parameters.from_warehouse_id,
        counterpart_previous_quantity=previous_source_quantity,
        counterpart_new_quantity=source_inventory.on_hand_quantity,
        mitigation_plan_id=plan.mitigation_code,
        parameters=parameters,
    )

    return ReallocateInventoryResult(
        mitigationPlanId=plan.mitigation_code,
        partId=parameters.part_id,
        transferredQuantity=parameters.quantity,
        sourceInventory=_build_result_position(
            inventory=source_inventory,
            warehouse_id=parameters.from_warehouse_id,
            previous_quantity=previous_source_quantity,
            new_quantity=source_inventory.on_hand_quantity,
        ),
        destinationInventory=_build_result_position(
            inventory=destination_inventory,
            warehouse_id=parameters.to_warehouse_id,
            previous_quantity=previous_destination_quantity,
            new_quantity=destination_inventory.on_hand_quantity,
        ),
        updatedSourceQuantity=source_inventory.on_hand_quantity,
        updatedDestinationQuantity=destination_inventory.on_hand_quantity,
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


def _load_part(
    context: ActionExecutionContext,
    part_id: str,
) -> Part:
    statement = select(Part).where(Part.part_code == part_id)
    part = context.session.execute(statement).scalar_one_or_none()
    if part is None:
        raise ObjectNotFoundError("Part", part_id)
    return part


def _load_warehouse(
    context: ActionExecutionContext,
    warehouse_id: str,
) -> Warehouse:
    statement = select(Warehouse).where(Warehouse.warehouse_code == warehouse_id)
    warehouse = context.session.execute(statement).scalar_one_or_none()
    if warehouse is None:
        raise ObjectNotFoundError("Warehouse", warehouse_id)
    return warehouse


def _load_inventory_pair_for_update(
    context: ActionExecutionContext,
    *,
    part: Part,
    source_warehouse: Warehouse,
    destination_warehouse: Warehouse,
    parameters: ReallocateInventoryParameters,
) -> tuple[Inventory, Inventory]:
    ordering = case(
        (Inventory.warehouse_id == source_warehouse.id, 0),
        (Inventory.warehouse_id == destination_warehouse.id, 1),
        else_=2,
    )
    statement = (
        select(Inventory)
        .where(
            Inventory.item_type == "part",
            Inventory.warehouse_id.in_((source_warehouse.id, destination_warehouse.id)),
            Inventory.part_id == part.id,
        )
        .order_by(ordering, Inventory.id.asc())
        .with_for_update()
    )

    source_inventory = None
    destination_inventory = None
    for inventory in context.session.execute(statement).scalars():
        if inventory.warehouse_id == source_warehouse.id:
            source_inventory = inventory
        elif inventory.warehouse_id == destination_warehouse.id:
            destination_inventory = inventory

    if source_inventory is None:
        raise ObjectNotFoundError(
            "InventoryPosition",
            f"{parameters.from_warehouse_id}:{parameters.part_id}",
        )
    if destination_inventory is None:
        raise ObjectNotFoundError(
            "InventoryPosition",
            f"{parameters.to_warehouse_id}:{parameters.part_id}",
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


def _calculate_transferable_quantity(inventory: Inventory) -> Decimal:
    return max(
        ZERO,
        inventory.on_hand_quantity - inventory.reserved_quantity - inventory.safety_stock_quantity,
    )


def _record_inventory_audit(
    *,
    context: ActionExecutionContext,
    inventory: Inventory,
    inventory_role: str,
    warehouse_id: str,
    part_id: str,
    previous_quantity: Decimal,
    new_quantity: Decimal,
    counterpart_warehouse_id: str,
    counterpart_previous_quantity: Decimal,
    counterpart_new_quantity: Decimal,
    mitigation_plan_id: str,
    parameters: ReallocateInventoryParameters,
) -> None:
    AuditRepository(context.session).create_audit_log(
        actor_user_id=_try_parse_uuid(context.actor.actor_id),
        execution_id=context.execution_id,
        action_type="reallocateInventory",
        object_type="inventory",
        object_id=inventory.id,
        previous_value=_build_audit_state(
            context=context,
            inventory_role=inventory_role,
            inventory=inventory,
            warehouse_id=warehouse_id,
            part_id=part_id,
            quantity=previous_quantity,
            counterpart_warehouse_id=counterpart_warehouse_id,
            counterpart_quantity=counterpart_previous_quantity,
            mitigation_plan_id=mitigation_plan_id,
            parameters=parameters,
        ),
        new_value=_build_audit_state(
            context=context,
            inventory_role=inventory_role,
            inventory=inventory,
            warehouse_id=warehouse_id,
            part_id=part_id,
            quantity=new_quantity,
            counterpart_warehouse_id=counterpart_warehouse_id,
            counterpart_quantity=counterpart_new_quantity,
            mitigation_plan_id=mitigation_plan_id,
            parameters=parameters,
        ),
        reason=parameters.reason,
    )


def _build_audit_state(
    *,
    context: ActionExecutionContext,
    inventory_role: str,
    inventory: Inventory,
    warehouse_id: str,
    part_id: str,
    quantity: Decimal,
    counterpart_warehouse_id: str,
    counterpart_quantity: Decimal,
    mitigation_plan_id: str,
    parameters: ReallocateInventoryParameters,
) -> dict[str, object]:
    return {
        "actor": context.actor.actor_id,
        "actionType": "reallocateInventory",
        "requestId": context.request_id,
        "inventoryRole": inventory_role,
        "objectId": str(inventory.id),
        "inventoryPositionId": str(inventory.id),
        "warehouseId": warehouse_id,
        "partId": part_id,
        "quantity": str(quantity),
        "requestedQuantity": str(parameters.quantity),
        "fromWarehouseId": parameters.from_warehouse_id,
        "toWarehouseId": parameters.to_warehouse_id,
        "counterpartWarehouseId": counterpart_warehouse_id,
        "counterpartQuantity": str(counterpart_quantity),
        "mitigationPlanId": mitigation_plan_id,
        "reason": parameters.reason,
        "reservedQuantity": str(inventory.reserved_quantity),
        "availableQuantity": str(quantity - inventory.reserved_quantity),
    }


def _build_result_position(
    *,
    inventory: Inventory,
    warehouse_id: str,
    previous_quantity: Decimal,
    new_quantity: Decimal,
) -> ReallocatedInventoryPosition:
    return ReallocatedInventoryPosition(
        inventoryPositionId=str(inventory.id),
        warehouseId=warehouse_id,
        previousQuantity=previous_quantity,
        newQuantity=new_quantity,
    )


def _try_parse_uuid(raw_value: str) -> UUID | None:
    try:
        return UUID(raw_value)
    except ValueError:
        return None
