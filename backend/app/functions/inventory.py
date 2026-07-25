"""Read-only inventory availability function handlers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.core.exceptions import ApplicationError
from app.repositories.function_repository import FunctionRepository
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.functions import (
    CalculateStockoutRiskParameters,
    CalculateStockoutRiskResult,
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityResult,
    StockoutRiskLedgerEntry,
    StockoutRiskScoreBreakdown,
    StockoutRiskScoreComponent,
    WarehouseAvailabilityEntry,
)

ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100")
WEIGHT_SHORTAGE_SEVERITY = Decimal("0.50")
WEIGHT_STOCKOUT_URGENCY = Decimal("0.25")
WEIGHT_SAFETY_STOCK_BREACH = Decimal("0.15")
WEIGHT_PART_CRITICALITY = Decimal("0.10")
PART_CRITICALITY_SCORES = {
    "low": Decimal("25"),
    "medium": Decimal("50"),
    "high": Decimal("75"),
    "critical": Decimal("100"),
}


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


class InvalidHorizonDateError(ApplicationError):
    """Raised when the requested horizon date is before execution time."""

    def __init__(self, horizon_date: date) -> None:
        super().__init__(
            code="INVALID_HORIZON_DATE",
            message="The horizon date must be on or after the execution date.",
            status_code=422,
            details={"horizonDate": horizon_date.isoformat()},
        )


@dataclass(frozen=True, slots=True)
class _LedgerMovement:
    date: date
    direction_rank: int
    movement_type: str
    reference_id: str
    quantity: Decimal


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


def calculate_stockout_risk(
    context: FunctionExecutionContext,
    parameters: CalculateStockoutRiskParameters,
) -> CalculateStockoutRiskResult:
    """Project warehouse-level part stockout risk through a horizon date."""

    executed_at_date = context.executed_at.date()
    if parameters.horizon_date < executed_at_date:
        raise InvalidHorizonDateError(parameters.horizon_date)

    repository = FunctionRepository(context.session)
    if not repository.part_exists(parameters.part_id):
        raise PartNotFoundError(parameters.part_id)
    if not repository.warehouse_exists(parameters.warehouse_id):
        raise WarehouseNotFoundError(parameters.warehouse_id)

    inventory_position = repository.get_part_inventory_position(
        parameters.part_id,
        parameters.warehouse_id,
    )
    current_available_quantity = inventory_position.available_quantity if inventory_position else ZERO
    safety_stock_quantity = inventory_position.safety_stock_quantity if inventory_position else ZERO

    inbound_rows = repository.get_open_inbound_purchase_orders_for_part_warehouse(
        parameters.part_id,
        parameters.warehouse_id,
        parameters.horizon_date,
    )
    demand_rows = repository.get_open_part_demands_for_warehouse(
        parameters.part_id,
        parameters.warehouse_id,
        parameters.horizon_date,
    )
    highest_bom_criticality = repository.get_highest_bom_criticality_for_part(parameters.part_id)

    projected_inbound_quantity = sum((row.open_quantity for row in inbound_rows), start=ZERO)
    projected_demand_quantity = sum((row.demand_quantity for row in demand_rows), start=ZERO)

    movements: list[_LedgerMovement] = []
    for row in inbound_rows:
        movements.append(
            _LedgerMovement(
                date=row.expected_delivery_date,
                direction_rank=0,
                movement_type="inbound",
                reference_id=row.purchase_order_id,
                quantity=row.open_quantity,
            )
        )
    for row in demand_rows:
        movements.append(
            _LedgerMovement(
                date=row.required_date,
                direction_rank=1,
                movement_type="demand",
                reference_id=row.order_id,
                quantity=row.demand_quantity,
            )
        )

    movements.sort(key=lambda item: (item.date, item.direction_rank, item.reference_id))

    running_quantity = current_available_quantity
    safety_stock_breach_date: date | None = None
    stockout_date: date | None = None
    ledger: list[StockoutRiskLedgerEntry] = []

    for movement in movements:
        if movement.movement_type == "inbound":
            running_quantity += movement.quantity
        else:
            running_quantity -= movement.quantity

        if safety_stock_breach_date is None and running_quantity < safety_stock_quantity:
            safety_stock_breach_date = movement.date
        if stockout_date is None and running_quantity <= ZERO:
            stockout_date = movement.date

        ledger.append(
            StockoutRiskLedgerEntry(
                date=movement.date,
                movementType=movement.movement_type,
                referenceId=movement.reference_id,
                quantity=movement.quantity,
                runningQuantity=running_quantity,
            )
        )

    projected_ending_quantity = running_quantity
    shortage_quantity = max(ZERO, -projected_ending_quantity)
    days_until_stockout = None if stockout_date is None else (stockout_date - executed_at_date).days

    shortage_severity_raw = _calculate_shortage_severity_score(shortage_quantity, projected_demand_quantity)
    stockout_urgency_raw = _calculate_stockout_urgency_score(days_until_stockout)
    safety_stock_breach_raw = _calculate_safety_stock_breach_score(
        projected_ending_quantity,
        safety_stock_quantity,
    )
    part_criticality_raw = PART_CRITICALITY_SCORES.get(highest_bom_criticality or "", ZERO)

    score_breakdown = StockoutRiskScoreBreakdown(
        shortageSeverity=_score_component(shortage_severity_raw, WEIGHT_SHORTAGE_SEVERITY),
        stockoutUrgency=_score_component(stockout_urgency_raw, WEIGHT_STOCKOUT_URGENCY),
        safetyStockBreach=_score_component(safety_stock_breach_raw, WEIGHT_SAFETY_STOCK_BREACH),
        partCriticality=_score_component(part_criticality_raw, WEIGHT_PART_CRITICALITY),
    )

    weighted_total = (
        score_breakdown.shortage_severity.weighted_score
        + score_breakdown.stockout_urgency.weighted_score
        + score_breakdown.safety_stock_breach.weighted_score
        + score_breakdown.part_criticality.weighted_score
    )
    risk_score = int(_clamp(weighted_total, ZERO, ONE_HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    risk_level = _map_risk_level(risk_score)
    if shortage_quantity == ZERO and projected_ending_quantity >= safety_stock_quantity:
        risk_score = 0
        risk_level = "none"

    return CalculateStockoutRiskResult(
        partId=parameters.part_id,
        warehouseId=parameters.warehouse_id,
        horizonDate=parameters.horizon_date,
        currentAvailableQuantity=current_available_quantity,
        projectedInboundQuantity=projected_inbound_quantity,
        projectedDemandQuantity=projected_demand_quantity,
        projectedEndingQuantity=projected_ending_quantity,
        safetyStockQuantity=safety_stock_quantity,
        shortageQuantity=shortage_quantity,
        safetyStockBreachDate=safety_stock_breach_date,
        stockoutDate=stockout_date,
        daysUntilStockout=days_until_stockout,
        riskScore=risk_score,
        riskLevel=risk_level,
        scoreBreakdown=score_breakdown,
        ledger=ledger,
        warnings=[],
    )


def _score_component(raw_score: Decimal, weight: Decimal) -> StockoutRiskScoreComponent:
    return StockoutRiskScoreComponent(
        rawScore=_clamp(raw_score, ZERO, ONE_HUNDRED),
        weight=weight,
        weightedScore=_clamp(raw_score, ZERO, ONE_HUNDRED) * weight,
    )



def _calculate_shortage_severity_score(shortage_quantity: Decimal, projected_demand_quantity: Decimal) -> Decimal:
    if projected_demand_quantity <= ZERO:
        return ZERO
    return _clamp((shortage_quantity / projected_demand_quantity) * ONE_HUNDRED, ZERO, ONE_HUNDRED)



def _calculate_stockout_urgency_score(days_until_stockout: int | None) -> Decimal:
    if days_until_stockout is None:
        return ZERO
    if days_until_stockout <= 0:
        return ONE_HUNDRED
    if days_until_stockout <= 3:
        return Decimal("80")
    if days_until_stockout <= 7:
        return Decimal("60")
    if days_until_stockout <= 14:
        return Decimal("40")
    if days_until_stockout <= 30:
        return Decimal("20")
    return ZERO



def _calculate_safety_stock_breach_score(projected_ending_quantity: Decimal, safety_stock_quantity: Decimal) -> Decimal:
    if safety_stock_quantity <= ZERO:
        return ZERO
    if projected_ending_quantity >= safety_stock_quantity:
        return ZERO
    return _clamp(((safety_stock_quantity - projected_ending_quantity) / safety_stock_quantity) * ONE_HUNDRED, ZERO, ONE_HUNDRED)



def _map_risk_level(risk_score: int) -> str:
    if risk_score <= 0:
        return "none"
    if risk_score <= 24:
        return "low"
    if risk_score <= 49:
        return "medium"
    if risk_score <= 74:
        return "high"
    return "critical"



def _clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))
