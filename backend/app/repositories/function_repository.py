"""Repository queries for ontology function handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.mitigation import MitigationPlanStep
from app.models.risk import RiskEvent
from app.models.supply_chain import (
    CustomerOrder,
    CustomerOrderItem,
    Inventory,
    Part,
    Product,
    ProductBomItem,
    PurchaseOrder,
    PurchaseOrderItem,
    Shipment,
    Supplier,
    SupplierPart,
    Warehouse,
)

ZERO = Decimal("0.00")
ACTIVE_WAREHOUSE_STATUS = "active"
ACTIVE_PART_STATUS = "active"
ACTIVE_PRODUCT_STATUS = "active"
ACTIVE_SUPPLIER_PART_STATUS = "active"
OPEN_CUSTOMER_ORDER_STATUSES = ("open", "allocated", "partially_allocated", "delayed")
OPEN_PURCHASE_ORDER_STATUSES = ("confirmed", "partially_received", "delayed")
EXPEDITABLE_PURCHASE_ORDER_STATUSES = ("confirmed", "partially_received", "delayed")
OPEN_SHIPMENT_STATUSES = ("planned", "allocated", "in_transit", "delayed")


@dataclass(frozen=True, slots=True)
class InventoryAvailabilityRow:
    """One warehouse inventory row resolved to public identifiers."""

    warehouse_id: str
    available_quantity: Decimal
    reserved_quantity: Decimal


@dataclass(frozen=True, slots=True)
class SupplierPartRow:
    """Supplier-part relation resolved to public identifiers."""

    supplier_part_id: str
    part_id: UUID
    part_code: str
    part_name: str


@dataclass(frozen=True, slots=True)
class PurchaseOrderSupplyRow:
    """Open purchase-order supply for one supplier part."""

    purchase_order_id: str
    supplier_id: UUID
    part_id: UUID
    expected_delivery_date: date | None
    open_quantity: Decimal


@dataclass(frozen=True, slots=True)
class DemandProjectionRow:
    """Projected part demand derived from open customer orders and BOM rows."""

    part_id: UUID
    warehouse_code: str
    required_date: date
    demand_quantity: Decimal


@dataclass(frozen=True, slots=True)
class WarehouseInventoryRow:
    """Available inventory for one part at one demand-serving warehouse."""

    part_id: UUID
    warehouse_code: str
    available_quantity: Decimal


@dataclass(frozen=True, slots=True)
class ProductBomRequirementRow:
    """One active BOM requirement for an active product."""

    product_id: UUID
    product_code: str
    product_name: str
    part_id: UUID
    part_code: str
    part_name: str
    part_criticality: str
    quantity_required: Decimal
    is_critical: bool


@dataclass(frozen=True, slots=True)
class ProductDemandRow:
    """Open demand aggregated at the product level."""

    product_id: UUID
    open_order_quantity: Decimal


@dataclass(frozen=True, slots=True)
class OpenOrderLineRow:
    """Open order-line demand for impacted-product allocation."""

    order_id: UUID
    order_code: str
    priority: str
    required_delivery_date: date
    order_date: date
    destination_warehouse_id: str | None
    order_line_id: UUID
    product_id: UUID
    product_code: str
    remaining_quantity: Decimal
    estimated_line_value: Decimal


class FunctionRepository:
    """Read-only repository for ontology function execution."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def part_exists(self, part_id: str) -> bool:
        statement = select(Part.id).where(Part.part_code == part_id)
        return self._session.execute(statement).scalar_one_or_none() is not None

    def get_risk_event_by_code(self, risk_event_id: str) -> RiskEvent | None:
        statement = select(RiskEvent).where(RiskEvent.risk_code == risk_event_id)
        return self._session.execute(statement).scalar_one_or_none()

    def supplier_exists(self, supplier_id: UUID) -> bool:
        statement = select(Supplier.id).where(Supplier.id == supplier_id)
        return self._session.execute(statement).scalar_one_or_none() is not None

    def get_active_supplier_parts(self, supplier_id: UUID) -> list[SupplierPartRow]:
        statement: Select[tuple[SupplierPart, Part]] = (
            select(SupplierPart, Part)
            .join(Part, Part.id == SupplierPart.part_id)
            .where(
                SupplierPart.supplier_id == supplier_id,
                SupplierPart.status == ACTIVE_SUPPLIER_PART_STATUS,
                Part.status == ACTIVE_PART_STATUS,
            )
            .order_by(Part.part_code.asc(), SupplierPart.supplier_part_code.asc(), SupplierPart.id.asc())
        )
        return [
            SupplierPartRow(
                supplier_part_id=supplier_part.supplier_part_code or str(supplier_part.id),
                part_id=part.id,
                part_code=part.part_code,
                part_name=part.name,
            )
            for supplier_part, part in self._session.execute(statement).all()
        ]

    def get_open_purchase_orders_for_parts(
        self,
        part_ids: set[UUID],
    ) -> list[PurchaseOrderSupplyRow]:
        if not part_ids:
            return []

        statement: Select[tuple[PurchaseOrder, PurchaseOrderItem]] = (
            select(PurchaseOrder, PurchaseOrderItem)
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(
                PurchaseOrder.status.in_(OPEN_PURCHASE_ORDER_STATUSES),
                PurchaseOrderItem.part_id.in_(part_ids),
            )
            .order_by(
                PurchaseOrder.expected_delivery_date.asc(),
                PurchaseOrder.purchase_order_code.asc(),
            )
        )

        rows: list[PurchaseOrderSupplyRow] = []
        for purchase_order, item in self._session.execute(statement).all():
            open_quantity = max(ZERO, item.quantity_ordered - item.quantity_received)
            if open_quantity <= ZERO:
                continue
            rows.append(
                PurchaseOrderSupplyRow(
                    purchase_order_id=purchase_order.purchase_order_code,
                    supplier_id=purchase_order.supplier_id,
                    part_id=item.part_id,
                    expected_delivery_date=purchase_order.expected_delivery_date,
                    open_quantity=open_quantity,
                )
            )
        return rows

    def get_open_part_demands(self, part_ids: set[UUID]) -> list[DemandProjectionRow]:
        if not part_ids:
            return []

        statement = (
            select(
                ProductBomItem.part_id,
                Warehouse.warehouse_code,
                CustomerOrder.requested_delivery_date,
                CustomerOrderItem.quantity_ordered,
                CustomerOrderItem.quantity_allocated,
                ProductBomItem.quantity_required,
            )
            .join(Product, Product.id == ProductBomItem.product_id)
            .join(CustomerOrderItem, CustomerOrderItem.product_id == Product.id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.order_id)
            .join(Shipment, Shipment.order_id == CustomerOrder.id)
            .join(Warehouse, Warehouse.id == Shipment.warehouse_id)
            .where(
                ProductBomItem.part_id.in_(part_ids),
                Product.status == ACTIVE_PRODUCT_STATUS,
                CustomerOrder.status.in_(OPEN_CUSTOMER_ORDER_STATUSES),
                Shipment.status.in_(OPEN_SHIPMENT_STATUSES),
                Warehouse.status == ACTIVE_WAREHOUSE_STATUS,
            )
            .order_by(
                CustomerOrder.requested_delivery_date.asc(),
                Warehouse.warehouse_code.asc(),
            )
        )

        rows: list[DemandProjectionRow] = []
        for part_id, warehouse_code, required_date, quantity_ordered, quantity_allocated, quantity_required in self._session.execute(statement).all():
            unfulfilled_quantity = max(ZERO, quantity_ordered - quantity_allocated)
            if unfulfilled_quantity <= ZERO:
                continue
            rows.append(
                DemandProjectionRow(
                    part_id=part_id,
                    warehouse_code=warehouse_code,
                    required_date=required_date,
                    demand_quantity=unfulfilled_quantity * quantity_required,
                )
            )
        return rows

    def get_inventory_for_part_warehouses(
        self,
        part_ids: set[UUID],
        warehouse_codes: set[str],
    ) -> list[WarehouseInventoryRow]:
        if not part_ids or not warehouse_codes:
            return []

        statement: Select[tuple[Inventory, Warehouse]] = (
            select(Inventory, Warehouse)
            .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
            .where(
                Inventory.item_type == "part",
                Inventory.part_id.in_(part_ids),
                Warehouse.warehouse_code.in_(warehouse_codes),
                Warehouse.status == ACTIVE_WAREHOUSE_STATUS,
            )
            .order_by(Warehouse.warehouse_code.asc())
        )

        rows: list[WarehouseInventoryRow] = []
        for inventory, warehouse in self._session.execute(statement).all():
            rows.append(
                WarehouseInventoryRow(
                    part_id=inventory.part_id,
                    warehouse_code=warehouse.warehouse_code,
                    available_quantity=max(
                        ZERO,
                        inventory.on_hand_quantity - inventory.reserved_quantity,
                    ),
                )
            )
        return rows

    def get_candidate_products_for_parts(
        self,
        part_ids: set[UUID],
    ) -> list[ProductBomRequirementRow]:
        if not part_ids:
            return []

        statement = (
            select(
                Product.id,
                Product.product_code,
                Product.name,
                Part.id,
                Part.part_code,
                Part.name,
                Part.criticality,
                ProductBomItem.quantity_required,
                ProductBomItem.is_critical,
            )
            .join(ProductBomItem, ProductBomItem.product_id == Product.id)
            .join(Part, Part.id == ProductBomItem.part_id)
            .where(
                ProductBomItem.part_id.in_(part_ids),
                Product.status == ACTIVE_PRODUCT_STATUS,
                Part.status == ACTIVE_PART_STATUS,
            )
            .order_by(Product.product_code.asc(), Part.part_code.asc())
        )

        return [
            ProductBomRequirementRow(
                product_id=product_id,
                product_code=product_code,
                product_name=product_name,
                part_id=part_id,
                part_code=part_code,
                part_name=part_name,
                part_criticality=part_criticality,
                quantity_required=quantity_required,
                is_critical=is_critical,
            )
            for (
                product_id,
                product_code,
                product_name,
                part_id,
                part_code,
                part_name,
                part_criticality,
                quantity_required,
                is_critical,
            ) in self._session.execute(statement).all()
        ]

    def get_active_product_bom_requirements(
        self,
        product_ids: set[UUID],
    ) -> list[ProductBomRequirementRow]:
        if not product_ids:
            return []

        statement = (
            select(
                Product.id,
                Product.product_code,
                Product.name,
                Part.id,
                Part.part_code,
                Part.name,
                Part.criticality,
                ProductBomItem.quantity_required,
                ProductBomItem.is_critical,
            )
            .join(ProductBomItem, ProductBomItem.product_id == Product.id)
            .join(Part, Part.id == ProductBomItem.part_id)
            .where(
                Product.id.in_(product_ids),
                Product.status == ACTIVE_PRODUCT_STATUS,
                Part.status == ACTIVE_PART_STATUS,
            )
            .order_by(Product.product_code.asc(), Part.part_code.asc())
        )

        return [
            ProductBomRequirementRow(
                product_id=product_id,
                product_code=product_code,
                product_name=product_name,
                part_id=part_id,
                part_code=part_code,
                part_name=part_name,
                part_criticality=part_criticality,
                quantity_required=quantity_required,
                is_critical=is_critical,
            )
            for (
                product_id,
                product_code,
                product_name,
                part_id,
                part_code,
                part_name,
                part_criticality,
                quantity_required,
                is_critical,
            ) in self._session.execute(statement).all()
        ]

    def get_open_product_demands(self, product_ids: set[UUID]) -> list[ProductDemandRow]:
        if not product_ids:
            return []

        statement = (
            select(
                Product.id,
                CustomerOrderItem.quantity_ordered,
                CustomerOrderItem.quantity_allocated,
            )
            .join(CustomerOrderItem, CustomerOrderItem.product_id == Product.id)
            .join(CustomerOrder, CustomerOrder.id == CustomerOrderItem.order_id)
            .join(Shipment, Shipment.order_id == CustomerOrder.id)
            .where(
                Product.id.in_(product_ids),
                Product.status == ACTIVE_PRODUCT_STATUS,
                CustomerOrder.status.in_(OPEN_CUSTOMER_ORDER_STATUSES),
                Shipment.status.in_(OPEN_SHIPMENT_STATUSES),
            )
            .order_by(Product.product_code.asc())
        )

        demand_by_product: dict[UUID, Decimal] = {}
        for product_id, quantity_ordered, quantity_allocated in self._session.execute(statement).all():
            unfulfilled_quantity = max(ZERO, quantity_ordered - quantity_allocated)
            if unfulfilled_quantity <= ZERO:
                continue
            demand_by_product[product_id] = demand_by_product.get(product_id, ZERO) + unfulfilled_quantity

        return [
            ProductDemandRow(
                product_id=product_id,
                open_order_quantity=open_order_quantity,
            )
            for product_id, open_order_quantity in demand_by_product.items()
        ]

    def get_open_order_lines_for_products(self, product_codes: set[str]) -> list[OpenOrderLineRow]:
        if not product_codes:
            return []

        statement = (
            select(
                CustomerOrder,
                CustomerOrderItem,
                Product,
                Shipment,
                Warehouse,
            )
            .join(CustomerOrderItem, CustomerOrderItem.order_id == CustomerOrder.id)
            .join(Product, Product.id == CustomerOrderItem.product_id)
            .outerjoin(Shipment, Shipment.order_id == CustomerOrder.id)
            .outerjoin(Warehouse, Warehouse.id == Shipment.warehouse_id)
            .where(
                CustomerOrder.status.in_(OPEN_CUSTOMER_ORDER_STATUSES),
                Product.status == ACTIVE_PRODUCT_STATUS,
                Product.product_code.in_(product_codes),
            )
            .order_by(
                CustomerOrder.priority.asc(),
                CustomerOrder.requested_delivery_date.asc(),
                CustomerOrder.created_at.asc(),
                CustomerOrder.order_code.asc(),
                CustomerOrderItem.id.asc(),
            )
        )

        rows_by_line_id: dict[UUID, OpenOrderLineRow] = {}
        for order, order_item, product, shipment, warehouse in self._session.execute(statement).all():
            remaining_quantity = max(ZERO, order_item.quantity_ordered - order_item.quantity_allocated)
            if remaining_quantity <= ZERO:
                continue

            destination_warehouse_id = warehouse.warehouse_code if warehouse is not None else None
            existing = rows_by_line_id.get(order_item.id)
            if existing is None:
                rows_by_line_id[order_item.id] = OpenOrderLineRow(
                    order_id=order.id,
                    order_code=order.order_code,
                    priority=order.priority,
                    required_delivery_date=order.requested_delivery_date,
                    order_date=order.created_at.date(),
                    destination_warehouse_id=destination_warehouse_id,
                    order_line_id=order_item.id,
                    product_id=product.id,
                    product_code=product.product_code,
                    remaining_quantity=remaining_quantity,
                    estimated_line_value=ZERO,
                )
                continue

            resolved_destination = existing.destination_warehouse_id
            if resolved_destination is None and destination_warehouse_id is not None:
                resolved_destination = destination_warehouse_id
            elif resolved_destination is not None and destination_warehouse_id is not None:
                resolved_destination = min(resolved_destination, destination_warehouse_id)

            rows_by_line_id[order_item.id] = OpenOrderLineRow(
                order_id=existing.order_id,
                order_code=existing.order_code,
                priority=existing.priority,
                required_delivery_date=existing.required_delivery_date,
                order_date=existing.order_date,
                destination_warehouse_id=resolved_destination,
                order_line_id=existing.order_line_id,
                product_id=existing.product_id,
                product_code=existing.product_code,
                remaining_quantity=existing.remaining_quantity,
                estimated_line_value=existing.estimated_line_value,
            )

        return list(rows_by_line_id.values())

    def get_inventory_availability(self, part_id: str) -> list[InventoryAvailabilityRow]:
        statement: Select[tuple[Warehouse, Inventory]] = (
            select(Warehouse, Inventory)
            .join(Inventory, Inventory.warehouse_id == Warehouse.id)
            .join(Part, Part.id == Inventory.part_id)
            .where(
                Inventory.item_type == "part",
                Warehouse.status == ACTIVE_WAREHOUSE_STATUS,
                Part.part_code == part_id,
            )
            .order_by(Warehouse.warehouse_code.asc())
        )

        rows: list[InventoryAvailabilityRow] = []
        for warehouse, inventory in self._session.execute(statement).all():
            available_quantity = max(
                ZERO,
                inventory.on_hand_quantity - inventory.reserved_quantity,
            )
            rows.append(
                InventoryAvailabilityRow(
                    warehouse_id=warehouse.warehouse_code,
                    available_quantity=available_quantity,
                    reserved_quantity=inventory.reserved_quantity,
                )
            )
        return rows

@dataclass(frozen=True, slots=True)
class PartInventoryPositionRow:
    """One part inventory position resolved for a specific warehouse."""

    available_quantity: Decimal
    safety_stock_quantity: Decimal


@dataclass(frozen=True, slots=True)
class StockoutPurchaseOrderRow:
    """One open inbound purchase-order movement for stockout risk."""

    purchase_order_id: str
    expected_delivery_date: date
    open_quantity: Decimal


@dataclass(frozen=True, slots=True)
class StockoutDemandRow:
    """One dated part-demand movement for stockout risk."""

    order_id: str
    required_date: date
    demand_quantity: Decimal



@dataclass(frozen=True, slots=True)
class AlternativeWarehouseInventoryRow:
    """One active warehouse inventory position for a candidate source warehouse."""

    warehouse_id: str
    warehouse_name: str
    region: str | None
    country: str | None
    available_quantity: Decimal
    safety_stock_quantity: Decimal


@dataclass(frozen=True, slots=True)
class CommittedTransferQuantityRow:
    """Committed outgoing transfer quantity for one source warehouse and part."""

    warehouse_id: str
    quantity: Decimal


@dataclass(frozen=True, slots=True)
class ExpeditablePurchaseOrderCandidateRow:
    """Aggregated purchase-order expedite candidate for one part."""

    purchase_order_id: str
    purchase_order_number: str
    supplier_id: str
    destination_warehouse_id: str | None
    current_expected_date: date
    open_quantity: Decimal
    current_remaining_value: Decimal


def _warehouse_exists(self: FunctionRepository, warehouse_id: str) -> bool:
    statement = select(Warehouse.id).where(Warehouse.warehouse_code == warehouse_id)
    return self._session.execute(statement).scalar_one_or_none() is not None



def _get_part_inventory_position(
    self: FunctionRepository,
    part_id: str,
    warehouse_id: str,
) -> PartInventoryPositionRow | None:
    statement = (
        select(Inventory)
        .join(Part, Part.id == Inventory.part_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(
            Inventory.item_type == "part",
            Part.part_code == part_id,
            Warehouse.warehouse_code == warehouse_id,
        )
    )
    inventory = self._session.execute(statement).scalar_one_or_none()
    if inventory is None:
        return None
    return PartInventoryPositionRow(
        available_quantity=max(ZERO, inventory.on_hand_quantity - inventory.reserved_quantity),
        safety_stock_quantity=inventory.safety_stock_quantity,
    )



def _get_open_inbound_purchase_orders_for_part_warehouse(
    self: FunctionRepository,
    part_id: str,
    warehouse_id: str,
    horizon_date: date,
) -> list[StockoutPurchaseOrderRow]:
    statement = (
        select(PurchaseOrder, PurchaseOrderItem)
        .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
        .join(Part, Part.id == PurchaseOrderItem.part_id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    statement = (
        select(PurchaseOrder, PurchaseOrderItem, Warehouse)
        .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
        .join(Part, Part.id == PurchaseOrderItem.part_id)
        .join(Inventory, Inventory.part_id == Part.id)
        .join(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(
            PurchaseOrder.status.in_(OPEN_PURCHASE_ORDER_STATUSES),
            PurchaseOrder.expected_delivery_date.is_not(None),
            PurchaseOrder.expected_delivery_date <= horizon_date,
            Inventory.item_type == "part",
            Part.part_code == part_id,
            Warehouse.warehouse_code == warehouse_id,
        )
        .order_by(
            PurchaseOrder.expected_delivery_date.asc(),
            PurchaseOrder.purchase_order_code.asc(),
            PurchaseOrderItem.id.asc(),
        )
    )
    rows: list[StockoutPurchaseOrderRow] = []
    for purchase_order, item, _warehouse in self._session.execute(statement).all():
        open_quantity = max(ZERO, item.quantity_ordered - item.quantity_received)
        if open_quantity <= ZERO or purchase_order.expected_delivery_date is None:
            continue
        rows.append(
            StockoutPurchaseOrderRow(
                purchase_order_id=purchase_order.purchase_order_code,
                expected_delivery_date=purchase_order.expected_delivery_date,
                open_quantity=open_quantity,
            )
        )
    return rows



def _get_open_part_demands_for_warehouse(
    self: FunctionRepository,
    part_id: str,
    warehouse_id: str,
    horizon_date: date,
) -> list[StockoutDemandRow]:
    statement = (
        select(
            CustomerOrder.order_code,
            CustomerOrder.requested_delivery_date,
            CustomerOrderItem.quantity_ordered,
            CustomerOrderItem.quantity_allocated,
            ProductBomItem.quantity_required,
        )
        .join(CustomerOrderItem, CustomerOrderItem.order_id == CustomerOrder.id)
        .join(Product, Product.id == CustomerOrderItem.product_id)
        .join(ProductBomItem, ProductBomItem.product_id == Product.id)
        .join(Part, Part.id == ProductBomItem.part_id)
        .join(Shipment, Shipment.order_id == CustomerOrder.id)
        .join(Warehouse, Warehouse.id == Shipment.warehouse_id)
        .where(
            CustomerOrder.status.in_(OPEN_CUSTOMER_ORDER_STATUSES),
            Shipment.status.in_(OPEN_SHIPMENT_STATUSES),
            Product.status == ACTIVE_PRODUCT_STATUS,
            Part.status == ACTIVE_PART_STATUS,
            Part.part_code == part_id,
            Warehouse.warehouse_code == warehouse_id,
            CustomerOrder.requested_delivery_date <= horizon_date,
        )
        .order_by(
            CustomerOrder.requested_delivery_date.asc(),
            CustomerOrder.order_code.asc(),
            CustomerOrderItem.id.asc(),
        )
    )
    rows: list[StockoutDemandRow] = []
    for order_code, required_date, quantity_ordered, quantity_allocated, quantity_required in self._session.execute(statement).all():
        remaining_quantity = max(ZERO, quantity_ordered - quantity_allocated)
        if remaining_quantity <= ZERO:
            continue
        rows.append(
            StockoutDemandRow(
                order_id=order_code,
                required_date=required_date,
                demand_quantity=remaining_quantity * quantity_required,
            )
        )
    return rows



def _get_highest_bom_criticality_for_part(self: FunctionRepository, part_id: str) -> str | None:
    statement = (
        select(Part.criticality)
        .join(ProductBomItem, ProductBomItem.part_id == Part.id)
        .join(Product, Product.id == ProductBomItem.product_id)
        .where(
            Part.part_code == part_id,
            Part.status == ACTIVE_PART_STATUS,
            Product.status == ACTIVE_PRODUCT_STATUS,
        )
        .limit(1)
    )
    return self._session.execute(statement).scalar_one_or_none()


FunctionRepository.warehouse_exists = _warehouse_exists
FunctionRepository.get_part_inventory_position = _get_part_inventory_position
FunctionRepository.get_open_inbound_purchase_orders_for_part_warehouse = _get_open_inbound_purchase_orders_for_part_warehouse
FunctionRepository.get_open_part_demands_for_warehouse = _get_open_part_demands_for_warehouse
FunctionRepository.get_highest_bom_criticality_for_part = _get_highest_bom_criticality_for_part


def _get_part_by_code(self: FunctionRepository, part_id: str) -> Part | None:
    statement = select(Part).where(Part.part_code == part_id)
    return self._session.execute(statement).scalar_one_or_none()


def _get_warehouse_by_code(self: FunctionRepository, warehouse_id: str) -> Warehouse | None:
    statement = select(Warehouse).where(Warehouse.warehouse_code == warehouse_id)
    return self._session.execute(statement).scalar_one_or_none()


def _get_source_inventory_positions_for_part(
    self: FunctionRepository,
    part_id: str,
    excluded_warehouse_id: str,
) -> list[AlternativeWarehouseInventoryRow]:
    statement: Select[tuple[Warehouse, Inventory]] = (
        select(Warehouse, Inventory)
        .join(Inventory, Inventory.warehouse_id == Warehouse.id)
        .join(Part, Part.id == Inventory.part_id)
        .where(
            Inventory.item_type == "part",
            Part.part_code == part_id,
            Warehouse.status == ACTIVE_WAREHOUSE_STATUS,
            Warehouse.warehouse_code != excluded_warehouse_id,
        )
        .order_by(Warehouse.warehouse_code.asc())
    )

    rows: list[AlternativeWarehouseInventoryRow] = []
    for warehouse, inventory in self._session.execute(statement).all():
        rows.append(
            AlternativeWarehouseInventoryRow(
                warehouse_id=warehouse.warehouse_code,
                warehouse_name=warehouse.name,
                region=warehouse.region,
                country=warehouse.country,
                available_quantity=max(ZERO, inventory.on_hand_quantity - inventory.reserved_quantity),
                safety_stock_quantity=inventory.safety_stock_quantity,
            )
        )
    return rows


def _get_committed_outgoing_transfer_quantities_for_part(
    self: FunctionRepository,
    part_id: str,
) -> dict[str, Decimal]:
    statement = (
        select(
            Warehouse.warehouse_code,
            func.coalesce(func.sum(MitigationPlanStep.quantity), 0),
        )
        .join(Warehouse, Warehouse.id == MitigationPlanStep.source_warehouse_id)
        .join(Part, Part.id == MitigationPlanStep.part_id)
        .where(
            MitigationPlanStep.action_type == "reallocate_inventory",
            MitigationPlanStep.status.in_(("approved", "executing")),
            Part.part_code == part_id,
            Warehouse.status == ACTIVE_WAREHOUSE_STATUS,
        )
        .group_by(Warehouse.warehouse_code)
    )
    return {warehouse_id: quantity for warehouse_id, quantity in self._session.execute(statement).all()}


FunctionRepository.get_part_by_code = _get_part_by_code
FunctionRepository.get_warehouse_by_code = _get_warehouse_by_code
FunctionRepository.get_source_inventory_positions_for_part = _get_source_inventory_positions_for_part
FunctionRepository.get_committed_outgoing_transfer_quantities_for_part = _get_committed_outgoing_transfer_quantities_for_part



def _get_supplier_by_code(self: FunctionRepository, supplier_id: str) -> Supplier | None:
    statement = select(Supplier).where(Supplier.supplier_code == supplier_id)
    return self._session.execute(statement).scalar_one_or_none()



def _get_expeditable_purchase_orders_for_part(
    self: FunctionRepository,
    part_id: str,
    supplier_id: str | None = None,
) -> list[ExpeditablePurchaseOrderCandidateRow]:
    statement = (
        select(
            PurchaseOrder.purchase_order_code,
            PurchaseOrder.purchase_order_code,
            Supplier.supplier_code,
            Warehouse.warehouse_code,
            PurchaseOrder.expected_delivery_date,
            PurchaseOrderItem.quantity_ordered,
            PurchaseOrderItem.quantity_received,
            PurchaseOrderItem.unit_cost,
        )
        .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
        .join(Part, Part.id == PurchaseOrderItem.part_id)
        .join(Supplier, Supplier.id == PurchaseOrder.supplier_id)
        .outerjoin(Inventory, (Inventory.part_id == Part.id) & (Inventory.item_type == "part"))
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
        .where(
            PurchaseOrder.status.in_(EXPEDITABLE_PURCHASE_ORDER_STATUSES),
            PurchaseOrder.expected_delivery_date.is_not(None),
            Part.part_code == part_id,
        )
        .order_by(
            PurchaseOrder.expected_delivery_date.asc(),
            PurchaseOrder.purchase_order_code.asc(),
            Warehouse.warehouse_code.asc(),
            PurchaseOrderItem.id.asc(),
        )
    )
    if supplier_id is not None:
        statement = statement.where(Supplier.supplier_code == supplier_id)

    aggregates: dict[str, dict[str, object]] = {}
    for (
        purchase_order_id,
        purchase_order_number,
        supplier_code,
        destination_warehouse_id,
        expected_delivery_date,
        quantity_ordered,
        quantity_received,
        unit_cost,
    ) in self._session.execute(statement).all():
        open_quantity = max(ZERO, quantity_ordered - quantity_received)
        if open_quantity <= ZERO or expected_delivery_date is None:
            continue

        aggregate = aggregates.setdefault(
            purchase_order_id,
            {
                "purchase_order_id": purchase_order_id,
                "purchase_order_number": purchase_order_number,
                "supplier_id": supplier_code,
                "destination_warehouse_id": destination_warehouse_id,
                "current_expected_date": expected_delivery_date,
                "open_quantity": ZERO,
                "current_remaining_value": ZERO,
            },
        )
        current_destination = aggregate["destination_warehouse_id"]
        if current_destination is None and destination_warehouse_id is not None:
            aggregate["destination_warehouse_id"] = destination_warehouse_id
        elif current_destination is not None and destination_warehouse_id is not None:
            aggregate["destination_warehouse_id"] = min(current_destination, destination_warehouse_id)

        aggregate["open_quantity"] = aggregate["open_quantity"] + open_quantity
        line_unit_cost = unit_cost if unit_cost is not None else ZERO
        aggregate["current_remaining_value"] = aggregate["current_remaining_value"] + (open_quantity * line_unit_cost)

    rows = [
        ExpeditablePurchaseOrderCandidateRow(
            purchase_order_id=aggregate["purchase_order_id"],
            purchase_order_number=aggregate["purchase_order_number"],
            supplier_id=aggregate["supplier_id"],
            destination_warehouse_id=aggregate["destination_warehouse_id"],
            current_expected_date=aggregate["current_expected_date"],
            open_quantity=aggregate["open_quantity"],
            current_remaining_value=aggregate["current_remaining_value"],
        )
        for aggregate in aggregates.values()
        if aggregate["open_quantity"] > ZERO
    ]
    rows.sort(
        key=lambda row: (
            row.current_expected_date,
            row.purchase_order_id,
            row.destination_warehouse_id or "",
        )
    )
    return rows


FunctionRepository.get_supplier_by_code = _get_supplier_by_code
FunctionRepository.get_expeditable_purchase_orders_for_part = _get_expeditable_purchase_orders_for_part
