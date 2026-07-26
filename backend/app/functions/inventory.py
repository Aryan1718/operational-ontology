"""Read-only inventory availability function handlers."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from app.core.exceptions import ApplicationError
from app.repositories.function_repository import FunctionRepository
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.functions import (
    AlternativeWarehouseEntry,
    AlternativeWarehouseEstimator,
    CalculateStockoutRiskParameters,
    CalculateStockoutRiskResult,
    ExpeditablePurchaseOrderEntry,
    ExpeditablePurchaseOrderEstimator,
    FindAlternativeWarehousesParameters,
    FindAlternativeWarehousesResult,
    FindExpeditablePurchaseOrdersParameters,
    FindExpeditablePurchaseOrdersResult,
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityResult,
    StockoutRiskLedgerEntry,
    StockoutRiskScoreBreakdown,
    StockoutRiskScoreComponent,
    WarehouseAvailabilityEntry,
)

ZERO = Decimal("0.00")
ONE_HUNDRED = Decimal("100")
MONEY_QUANTUM = Decimal("0.01")
TRANSFER_ESTIMATOR_NAME = "region-country-transfer-estimator"
TRANSFER_ESTIMATOR_ASSUMPTIONS = [
    "Same-region transfers require 1 day",
    "Same-country transfers require 2 days",
    "Cross-country transfers require 5 days",
]
TRANSFER_BASE_COST = Decimal("50.00")
TRANSFER_COST_PER_UNIT_PER_DAY = Decimal("0.10")
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

EXPEDITE_ESTIMATOR_NAME = "configured-expedite-estimator"
EXPEDITE_ESTIMATOR_ASSUMPTIONS = [
    "Expedited dates and costs are estimates",
    "Supplier acceptance is not guaranteed",
]


@dataclass(frozen=True, slots=True)
class _ExpediteEstimatorConfig:
    lead_time_reduction_percent: Decimal
    premium_percent: Decimal
    minimum_lead_time_days: int


DEFAULT_EXPEDITE_ESTIMATOR = _ExpediteEstimatorConfig(
    lead_time_reduction_percent=Decimal("0.40"),
    premium_percent=Decimal("0.15"),
    minimum_lead_time_days=1,
)


class PartNotFoundError(ApplicationError):
    """Raised when a public part identifier does not resolve."""

    def __init__(self, part_id: str) -> None:
        super().__init__(
            code="PART_NOT_FOUND",
            message=f"Part '{part_id}' was not found.",
            status_code=404,
            details={"partId": part_id},
        )


class SupplierNotFoundError(ApplicationError):
    """Raised when a public supplier identifier does not resolve."""

    def __init__(self, supplier_id: str) -> None:
        super().__init__(
            code="SUPPLIER_NOT_FOUND",
            message=f"Supplier '{supplier_id}' was not found.",
            status_code=404,
            details={"supplierId": supplier_id},
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




def find_alternative_warehouses(
    context: FunctionExecutionContext,
    parameters: FindAlternativeWarehousesParameters,
) -> FindAlternativeWarehousesResult:
    """Return feasible source warehouses that can transfer part inventory safely."""

    repository = FunctionRepository(context.session)
    part = repository.get_part_by_code(parameters.part_id)
    if part is None:
        raise PartNotFoundError(parameters.part_id)

    destination = repository.get_warehouse_by_code(parameters.destination_warehouse_id)
    if destination is None:
        raise WarehouseNotFoundError(parameters.destination_warehouse_id)

    executed_at_date = context.executed_at.date()
    committed_by_warehouse = repository.get_committed_outgoing_transfer_quantities_for_part(parameters.part_id)
    source_rows = repository.get_source_inventory_positions_for_part(
        parameters.part_id,
        parameters.destination_warehouse_id,
    )

    items: list[AlternativeWarehouseEntry] = []
    for row in source_rows:
        estimated_transfer_days = _estimate_transfer_days(
            source_region=row.region,
            source_country=row.country,
            destination_region=destination.region,
            destination_country=destination.country,
        )
        estimated_arrival_date = executed_at_date + timedelta(days=estimated_transfer_days)
        if estimated_arrival_date > parameters.required_by_date:
            continue

        latest_departure_date = parameters.required_by_date - timedelta(days=estimated_transfer_days)
        inbound_rows = repository.get_open_inbound_purchase_orders_for_part_warehouse(
            parameters.part_id,
            row.warehouse_id,
            latest_departure_date,
        )
        eligible_source_inbound_quantity = sum((movement.open_quantity for movement in inbound_rows), start=ZERO)
        committed_outgoing_transfer_quantity = committed_by_warehouse.get(row.warehouse_id, ZERO)
        transferable_quantity = max(
            ZERO,
            row.available_quantity
            + eligible_source_inbound_quantity
            - row.safety_stock_quantity
            - committed_outgoing_transfer_quantity,
        )
        if transferable_quantity <= ZERO:
            continue

        covered_quantity = min(parameters.required_quantity, transferable_quantity)
        remaining_shortage = max(ZERO, parameters.required_quantity - covered_quantity)
        estimated_transfer_cost = (
            TRANSFER_BASE_COST
            + (covered_quantity * TRANSFER_COST_PER_UNIT_PER_DAY * Decimal(estimated_transfer_days))
        ).quantize(MONEY_QUANTUM)

        items.append(
            AlternativeWarehouseEntry(
                warehouseId=row.warehouse_id,
                warehouseName=row.warehouse_name,
                availableQuantity=row.available_quantity,
                safetyStockQuantity=row.safety_stock_quantity,
                committedOutgoingTransferQuantity=committed_outgoing_transfer_quantity,
                transferableQuantity=transferable_quantity,
                coveredQuantity=covered_quantity,
                remainingShortage=remaining_shortage,
                estimatedTransferDays=estimated_transfer_days,
                estimatedArrivalDate=estimated_arrival_date,
                estimatedTransferCost=estimated_transfer_cost,
                feasible=True,
                infeasibilityReasons=[],
                estimator=AlternativeWarehouseEstimator(
                    name=TRANSFER_ESTIMATOR_NAME,
                    assumptions=TRANSFER_ESTIMATOR_ASSUMPTIONS,
                ),
            )
        )

    items.sort(
        key=lambda item: (
            0 if item.covered_quantity >= parameters.required_quantity else 1,
            item.estimated_arrival_date,
            item.estimated_transfer_cost,
            -item.transferable_quantity,
            item.warehouse_id,
        )
    )
    return FindAlternativeWarehousesResult(items=items)


def _estimate_transfer_days(
    *,
    source_region: str | None,
    source_country: str | None,
    destination_region: str | None,
    destination_country: str | None,
) -> int:
    if source_region and destination_region and source_country and destination_country:
        if source_region == destination_region and source_country == destination_country:
            return 1
    if source_country and destination_country and source_country == destination_country:
        return 2
    return 5

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



def find_expeditable_purchase_orders(
    context: FunctionExecutionContext,
    parameters: FindExpeditablePurchaseOrdersParameters,
) -> FindExpeditablePurchaseOrdersResult:
    """Return eligible purchase-order expedite candidates for the requested part."""

    repository = FunctionRepository(context.session)
    if not repository.part_exists(parameters.part_id):
        raise PartNotFoundError(parameters.part_id)
    if parameters.supplier_id is not None and repository.get_supplier_by_code(parameters.supplier_id) is None:
        raise SupplierNotFoundError(parameters.supplier_id)

    executed_at_date = context.executed_at.date()
    candidates = repository.get_expeditable_purchase_orders_for_part(
        parameters.part_id,
        parameters.supplier_id,
    )

    items: list[ExpeditablePurchaseOrderEntry] = []
    estimator = ExpeditablePurchaseOrderEstimator(
        name=EXPEDITE_ESTIMATOR_NAME,
        leadTimeReductionPercent=DEFAULT_EXPEDITE_ESTIMATOR.lead_time_reduction_percent,
        premiumPercent=DEFAULT_EXPEDITE_ESTIMATOR.premium_percent,
        minimumLeadTimeDays=DEFAULT_EXPEDITE_ESTIMATOR.minimum_lead_time_days,
        assumptions=EXPEDITE_ESTIMATOR_ASSUMPTIONS,
    )

    for candidate in candidates:
        remaining_lead_time_days = max(0, (candidate.current_expected_date - executed_at_date).days)
        reduced_days = floor(
            Decimal(remaining_lead_time_days) * DEFAULT_EXPEDITE_ESTIMATOR.lead_time_reduction_percent
        )
        expedited_lead_time_days = max(
            DEFAULT_EXPEDITE_ESTIMATOR.minimum_lead_time_days,
            remaining_lead_time_days - reduced_days,
        )
        possible_expedited_date = executed_at_date + timedelta(days=expedited_lead_time_days)
        days_saved = max(0, (candidate.current_expected_date - possible_expedited_date).days)
        additional_cost = (
            candidate.current_remaining_value * DEFAULT_EXPEDITE_ESTIMATOR.premium_percent
        ).quantize(MONEY_QUANTUM)
        feasible = possible_expedited_date <= parameters.required_by_date
        infeasibility_reasons = [] if feasible else [
            (
                'possibleExpeditedDate exceeds requiredByDate '
                f'({possible_expedited_date.isoformat()} > {parameters.required_by_date.isoformat()})'
            )
        ]

        items.append(
            ExpeditablePurchaseOrderEntry(
                purchaseOrderId=candidate.purchase_order_id,
                purchaseOrderNumber=candidate.purchase_order_number,
                supplierId=candidate.supplier_id,
                destinationWarehouseId=candidate.destination_warehouse_id,
                openQuantity=candidate.open_quantity,
                currentExpectedDate=candidate.current_expected_date,
                possibleExpeditedDate=possible_expedited_date,
                daysSaved=days_saved,
                currentRemainingValue=candidate.current_remaining_value.quantize(MONEY_QUANTUM),
                additionalCost=additional_cost,
                feasible=feasible,
                infeasibilityReasons=infeasibility_reasons,
                estimator=estimator,
            )
        )

    items.sort(
        key=lambda item: (
            0 if item.feasible else 1,
            item.possible_expedited_date,
            item.additional_cost,
            -item.open_quantity,
            item.purchase_order_id,
        )
    )
    return FindExpeditablePurchaseOrdersResult(items=items)
