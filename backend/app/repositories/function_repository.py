"""Repository queries for ontology function handlers."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.supply_chain import Inventory, Part, Warehouse

ZERO = Decimal("0.00")
ACTIVE_WAREHOUSE_STATUS = "active"


@dataclass(frozen=True, slots=True)
class InventoryAvailabilityRow:
    """One warehouse inventory row resolved to public identifiers."""

    warehouse_id: str
    available_quantity: Decimal
    reserved_quantity: Decimal


class FunctionRepository:
    """Read-only repository for ontology function execution."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def part_exists(self, part_id: str) -> bool:
        statement = select(Part.id).where(Part.part_code == part_id)
        return self._session.execute(statement).scalar_one_or_none() is not None

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
