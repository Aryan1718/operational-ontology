"""Read-only inventory availability function handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.models.supply_chain import (
    Inventory,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    Warehouse,
)
from app.repositories.object_repository import ObjectRepository
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.functions import (
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityItem,
)

ZERO = Decimal("0.00")
OPEN_PURCHASE_ORDER_STATUSES = ("open", "confirmed", "partially_received", "delayed")
ACTIVE_WAREHOUSE_STATUS = "active"


class PartNotFoundError(ApplicationError):
    """Raised when a public part identifier does not resolve."""

    def __init__(self, part_id: str) -> None:
        super().__init__(
            code="PART_NOT_FOUND",
            message=f"Part '{part_id}' was not found.",
            status_code=404,
            details={"partId": part_id},
        )


class WarehouseNotFoundError(ApplicationError):
    """Raised when a public warehouse identifier does not resolve."""

    def __init__(self, warehouse_id: str) -> None:
        super().__init__(
            code="WAREHOUSE_NOT_FOUND",
            message=f"Warehouse '{warehouse_id}' was not found.",
            status_code=404,
            details={"warehouseId": warehouse_id},
        )


@dataclass(frozen=True, slots=True)
class _WarehouseAvailabilityRow:
    """Intermediate warehouse availability projection."""

    warehouse_id: str
    warehouse_name: str
    on_hand_quantity: Decimal
    reserved_quantity: Decimal
    safety_stock_quantity: Decimal
    inventory_updated_at: datetime
    eligible_inbound_quantity: Decimal

    @property
    def available_quantity(self) -> Decimal:
        return max(ZERO, self.on_hand_quantity - self.reserved_quantity)


def get_inventory_availability(
    context: FunctionExecutionContext,
    parameters: GetInventoryAvailabilityParameters,
) -> list[InventoryAvailabilityItem]:
    """Return current or date-aware inventory availability for one part."""

    repository = ObjectRepository(context.session)
    part_definition = context.registry.get_object_type("Part")
    warehouse_definition = context.registry.get_object_type("Warehouse")
    if part_definition is None or warehouse_definition is None:
        raise RuntimeError("Required ontology object mappings are missing.")

    part_mapping = repository.resolve_object_mapping(part_definition)
    warehouse_mapping = repository.resolve_object_mapping(warehouse_definition)
    part = repository.get_one(
        model=part_mapping.model,
        identifier_column=part_mapping.identifier_column,
        object_id=parameters.part_id,
        row_filter=part_definition.source.rowFilter,
    )
    if part is None:
        raise PartNotFoundError(parameters.part_id)

    warehouse = None
    if parameters.warehouse_id is not None:
        warehouse = repository.get_one(
            model=warehouse_mapping.model,
            identifier_column=warehouse_mapping.identifier_column,
            object_id=parameters.warehouse_id,
            row_filter=warehouse_definition.source.rowFilter,
        )
        if warehouse is None:
            raise WarehouseNotFoundError(parameters.warehouse_id)

    rows = _load_inventory_rows(
        session=context.session,
        part=part,
        warehouse=warehouse,
        required_by_date=parameters.required_by_date,
    )
    items = [
        _map_inventory_item(
            row=row,
            part_id=parameters.part_id,
            required_by_date=parameters.required_by_date,
        )
        for row in rows
    ]
    if parameters.required_by_date is None:
        return sorted(
            items,
            key=lambda item: (
                -item.available_quantity,
                -(
                    item.inventory_updated_at.timestamp()
                    if item.inventory_updated_at is not None
                    else float("-inf")
                ),
                item.warehouse_id,
            ),
        )
    return sorted(
        items,
        key=lambda item: (
            -(item.projected_available_by_required_date or ZERO),
            -(
                item.inventory_updated_at.timestamp()
                if item.inventory_updated_at is not None
                else float("-inf")
            ),
            item.warehouse_id,
        ),
    )


def _load_inventory_rows(
    *,
    session: Session,
    part: Part,
    warehouse: Warehouse | None,
    required_by_date: date | None,
) -> list[_WarehouseAvailabilityRow]:
    statement: Select[tuple[Inventory, Warehouse]] = (
        select(Inventory, Warehouse)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(
            Inventory.item_type == "part",
            Inventory.part_id == part.id,
        )
    )
    if warehouse is None:
        statement = statement.where(Warehouse.status == ACTIVE_WAREHOUSE_STATUS)
    else:
        statement = statement.where(Warehouse.id == warehouse.id)

    inventory_rows = session.execute(statement).all()
    if not inventory_rows:
        return []

    eligible_inbound_quantity = ZERO
    if warehouse is not None and required_by_date is not None:
        eligible_inbound_quantity = _load_eligible_inbound_quantity(
            session=session,
            part_id=part.id,
            required_by_date=required_by_date,
        )

    rows: list[_WarehouseAvailabilityRow] = []
    for inventory, inventory_warehouse in inventory_rows:
        inventory_updated_at = inventory.updated_at
        if inventory_updated_at.tzinfo is None:
            inventory_updated_at = inventory_updated_at.replace(tzinfo=UTC)
        rows.append(
            _WarehouseAvailabilityRow(
                warehouse_id=inventory_warehouse.warehouse_code,
                warehouse_name=inventory_warehouse.name,
                on_hand_quantity=inventory.on_hand_quantity,
                reserved_quantity=inventory.reserved_quantity,
                safety_stock_quantity=inventory.safety_stock_quantity,
                inventory_updated_at=inventory_updated_at,
                eligible_inbound_quantity=eligible_inbound_quantity
                if warehouse is not None
                else ZERO,
            )
        )
    return rows


def _load_eligible_inbound_quantity(
    *,
    session: Session,
    part_id: object,
    required_by_date: date,
) -> Decimal:
    statement = (
        select(PurchaseOrderItem, PurchaseOrder)
        .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
        .where(
            PurchaseOrderItem.part_id == part_id,
            PurchaseOrder.status.in_(OPEN_PURCHASE_ORDER_STATUSES),
            PurchaseOrder.expected_delivery_date.is_not(None),
            PurchaseOrder.expected_delivery_date <= required_by_date,
        )
    )
    total = ZERO
    for purchase_order_item, _purchase_order in session.execute(statement).all():
        total += max(
            ZERO,
            (
                purchase_order_item.quantity_ordered
                - purchase_order_item.quantity_received
            ),
        )
    return total


def _map_inventory_item(
    *,
    row: _WarehouseAvailabilityRow,
    part_id: str,
    required_by_date: date | None,
) -> InventoryAvailabilityItem:
    available_quantity = row.available_quantity
    warnings: list[str] = []
    if required_by_date is not None and row.eligible_inbound_quantity == ZERO:
        warnings.append(
            "No warehouse-specific inbound movement records were available "
            "beyond purchase-order dates."
        )
    if required_by_date is None:
        return InventoryAvailabilityItem(
            warehouseId=row.warehouse_id,
            warehouseName=row.warehouse_name,
            partId=part_id,
            onHandQuantity=row.on_hand_quantity,
            reservedQuantity=row.reserved_quantity,
            availableQuantity=available_quantity,
            inTransitQuantity=ZERO,
            inventoryUpdatedAt=row.inventory_updated_at,
            warnings=warnings,
        )

    projected_available = available_quantity + row.eligible_inbound_quantity
    surplus_above_safety_stock = max(
        ZERO,
        projected_available - row.safety_stock_quantity,
    )
    return InventoryAvailabilityItem(
        warehouseId=row.warehouse_id,
        warehouseName=row.warehouse_name,
        partId=part_id,
        onHandQuantity=row.on_hand_quantity,
        reservedQuantity=row.reserved_quantity,
        availableQuantity=available_quantity,
        inTransitQuantity=ZERO,
        eligibleInboundQuantity=row.eligible_inbound_quantity,
        eligibleIncomingTransferQuantity=ZERO,
        committedOutgoingTransferQuantity=ZERO,
        projectedAvailableByRequiredDate=projected_available,
        safetyStockQuantity=row.safety_stock_quantity,
        surplusAboveSafetyStock=surplus_above_safety_stock,
        inventoryUpdatedAt=row.inventory_updated_at,
        requiredByDate=required_by_date,
        warnings=warnings,
    )
