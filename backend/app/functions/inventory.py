"""Read-only inventory availability function handlers."""

from __future__ import annotations

from decimal import Decimal

from app.core.exceptions import ApplicationError
from app.repositories.function_repository import FunctionRepository
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.functions import (
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityResult,
    WarehouseAvailabilityEntry,
)

ZERO = Decimal("0.00")


class PartNotFoundError(ApplicationError):
    """Raised when a public part identifier does not resolve."""

    def __init__(self, part_id: str) -> None:
        super().__init__(
            code="PART_NOT_FOUND",
            message=f"Part '{part_id}' was not found.",
            status_code=404,
            details={"partId": part_id},
        )


def get_inventory_availability(
    context: FunctionExecutionContext,
    parameters: GetInventoryAvailabilityParameters,
) -> InventoryAvailabilityResult:
    """Return current inventory availability for one part across warehouses."""

    repository = FunctionRepository(context.session)
    if not repository.part_exists(parameters.part_id):
        raise PartNotFoundError(parameters.part_id)

    rows = repository.get_inventory_availability(parameters.part_id)
    warehouses = [
        WarehouseAvailabilityEntry(
            warehouseId=row.warehouse_id,
            availableQuantity=row.available_quantity,
            reservedQuantity=row.reserved_quantity,
        )
        for row in rows
    ]
    total_available_quantity = sum(
        (row.available_quantity for row in rows),
        start=ZERO,
    )
    return InventoryAvailabilityResult(
        partId=parameters.part_id,
        totalAvailableQuantity=total_available_quantity,
        warehouses=warehouses,
    )
