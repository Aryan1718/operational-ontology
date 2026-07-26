"""Pydantic schemas for ontology function execution."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.common import ApiBaseModel


class FunctionExecutionRequest(ApiBaseModel):
    """Strict generic request body for public ontology function execution."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    parameters: dict[str, Any] = Field(default_factory=dict)


class FunctionExecutionResponse(ApiBaseModel):
    """Shared successful payload returned from the function runtime."""

    function_name: str = Field(alias="functionName")
    result: Any
    warnings: list[str] = Field(default_factory=list)


class FindImpactedPartsParameters(ApiBaseModel):
    """Stable public input for findImpactedParts."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    risk_event_id: str = Field(alias="riskEventId", strict=True, min_length=1)


class ImpactedPartEntry(ApiBaseModel):
    """One impacted part returned from the supplier-delay projection."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", min_length=1)
    part_name: str = Field(alias="partName", min_length=1)
    supplier_part_id: str = Field(alias="supplierPartId", min_length=1)
    delay_days: int = Field(alias="delayDays", ge=0)
    open_purchase_order_quantity: Decimal = Field(alias="openPurchaseOrderQuantity")
    baseline_shortage_quantity: Decimal = Field(alias="baselineShortageQuantity")
    delayed_shortage_quantity: Decimal = Field(alias="delayedShortageQuantity")
    shortage_increase_quantity: Decimal = Field(alias="shortageIncreaseQuantity")
    first_baseline_shortage_date: date | None = Field(
        alias="firstBaselineShortageDate",
        default=None,
    )
    first_delayed_shortage_date: date | None = Field(
        alias="firstDelayedShortageDate",
        default=None,
    )
    delayed_purchase_order_ids: list[str] = Field(
        alias="delayedPurchaseOrderIds",
        default_factory=list,
    )
    impact_reason: str = Field(alias="impactReason", min_length=1)


class FindImpactedPartsResult(ApiBaseModel):
    """Read-only impacted-parts result set."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[ImpactedPartEntry] = Field(default_factory=list)


class FindImpactedProductsParameters(ApiBaseModel):
    """Stable public input for findImpactedProducts."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    risk_event_id: str = Field(alias="riskEventId", strict=True, min_length=1)


class ImpactedProductEntry(ApiBaseModel):
    """One impacted product derived from part-level projections."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    product_id: str = Field(alias="productId", min_length=1)
    product_name: str = Field(alias="productName", min_length=1)
    impacted_part_ids: list[str] = Field(alias="impactedPartIds", default_factory=list)
    required_quantities: dict[str, Decimal] = Field(alias="requiredQuantities", default_factory=dict)
    limiting_part_id: str = Field(alias="limitingPartId", min_length=1)
    baseline_maximum_buildable_quantity: Decimal = Field(alias="baselineMaximumBuildableQuantity")
    delayed_maximum_buildable_quantity: Decimal = Field(alias="delayedMaximumBuildableQuantity")
    open_order_quantity: Decimal = Field(alias="openOrderQuantity")
    baseline_production_shortfall_quantity: Decimal = Field(alias="baselineProductionShortfallQuantity")
    delayed_production_shortfall_quantity: Decimal = Field(alias="delayedProductionShortfallQuantity")
    shortfall_increase_quantity: Decimal = Field(alias="shortfallIncreaseQuantity")
    highest_part_criticality: str = Field(alias="highestPartCriticality", min_length=1)
    product_risk_level: str = Field(alias="productRiskLevel", min_length=1)
    impact_reason: str = Field(alias="impactReason", min_length=1)


class FindImpactedProductsResult(ApiBaseModel):
    """Read-only impacted-products result set."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[ImpactedProductEntry] = Field(default_factory=list)


class FindImpactedOrdersParameters(ApiBaseModel):
    """Stable public input for findImpactedOrders."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    risk_event_id: str = Field(alias="riskEventId", strict=True, min_length=1)


class ImpactedOrderProductEntry(ApiBaseModel):
    """One impacted product allocation within an impacted order."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    product_id: str = Field(alias="productId", min_length=1)
    required_quantity: Decimal = Field(alias="requiredQuantity")
    baseline_fulfillable_quantity: Decimal = Field(alias="baselineFulfillableQuantity")
    delayed_fulfillable_quantity: Decimal = Field(alias="delayedFulfillableQuantity")
    shortage_quantity: Decimal = Field(alias="shortageQuantity")


class ImpactedOrderEntry(ApiBaseModel):
    """One customer order whose impacted-product fulfillment worsens."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    order_id: str = Field(alias="orderId", min_length=1)
    order_number: str = Field(alias="orderNumber", min_length=1)
    priority: str = Field(min_length=1)
    required_delivery_date: date = Field(alias="requiredDeliveryDate")
    destination_warehouse_id: str | None = Field(alias="destinationWarehouseId", default=None)
    impacted_products: list[ImpactedOrderProductEntry] = Field(alias="impactedProducts", default_factory=list)
    impacted_part_ids: list[str] = Field(alias="impactedPartIds", default_factory=list)
    required_quantity: Decimal = Field(alias="requiredQuantity")
    baseline_fulfillable_quantity: Decimal = Field(alias="baselineFulfillableQuantity")
    delayed_fulfillable_quantity: Decimal = Field(alias="delayedFulfillableQuantity")
    shortage_quantity: Decimal = Field(alias="shortageQuantity")
    shortage_ratio: Decimal = Field(alias="shortageRatio")
    baseline_projected_delay_days: int = Field(alias="baselineProjectedDelayDays", ge=0)
    projected_delay_days: int = Field(alias="projectedDelayDays", ge=0)
    estimated_order_value: Decimal = Field(alias="estimatedOrderValue")
    risk_score: int = Field(alias="riskScore", ge=0, le=100)
    impact_reason: str = Field(alias="impactReason", min_length=1)
    warnings: list[str] = Field(default_factory=list)


class FindImpactedOrdersResult(ApiBaseModel):
    """Read-only impacted-orders result set."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[ImpactedOrderEntry] = Field(default_factory=list)


class GetInventoryAvailabilityParameters(ApiBaseModel):
    """Stable public input for getInventoryAvailability."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", strict=True, min_length=1)


class CalculateStockoutRiskParameters(ApiBaseModel):
    """Stable public input for calculateStockoutRisk."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", strict=True, min_length=1)
    warehouse_id: str = Field(alias="warehouseId", strict=True, min_length=1)
    horizon_date: date = Field(alias="horizonDate")


class StockoutRiskScoreComponent(ApiBaseModel):
    """One weighted scoring component for stockout risk."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    raw_score: Decimal = Field(alias="rawScore")
    weight: Decimal
    weighted_score: Decimal = Field(alias="weightedScore")


class StockoutRiskScoreBreakdown(ApiBaseModel):
    """Explainability fields for the stockout risk score."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    shortage_severity: StockoutRiskScoreComponent = Field(alias="shortageSeverity")
    stockout_urgency: StockoutRiskScoreComponent = Field(alias="stockoutUrgency")
    safety_stock_breach: StockoutRiskScoreComponent = Field(alias="safetyStockBreach")
    part_criticality: StockoutRiskScoreComponent = Field(alias="partCriticality")


class StockoutRiskLedgerEntry(ApiBaseModel):
    """One dated movement in the stockout projection ledger."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    date: date
    movement_type: str = Field(alias="movementType", min_length=1)
    reference_id: str = Field(alias="referenceId", min_length=1)
    quantity: Decimal
    running_quantity: Decimal = Field(alias="runningQuantity")


class CalculateStockoutRiskResult(ApiBaseModel):
    """Stable public output for calculateStockoutRisk."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", min_length=1)
    warehouse_id: str = Field(alias="warehouseId", min_length=1)
    horizon_date: date = Field(alias="horizonDate")
    current_available_quantity: Decimal = Field(alias="currentAvailableQuantity")
    projected_inbound_quantity: Decimal = Field(alias="projectedInboundQuantity")
    projected_demand_quantity: Decimal = Field(alias="projectedDemandQuantity")
    projected_ending_quantity: Decimal = Field(alias="projectedEndingQuantity")
    safety_stock_quantity: Decimal = Field(alias="safetyStockQuantity")
    shortage_quantity: Decimal = Field(alias="shortageQuantity")
    safety_stock_breach_date: date | None = Field(alias="safetyStockBreachDate", default=None)
    stockout_date: date | None = Field(alias="stockoutDate", default=None)
    days_until_stockout: int | None = Field(alias="daysUntilStockout", default=None)
    risk_score: int = Field(alias="riskScore", ge=0, le=100)
    risk_level: str = Field(alias="riskLevel", min_length=1)
    score_breakdown: StockoutRiskScoreBreakdown = Field(alias="scoreBreakdown")
    ledger: list[StockoutRiskLedgerEntry] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WarehouseAvailabilityEntry(ApiBaseModel):
    """Warehouse-level availability for one part."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    warehouse_id: str = Field(alias="warehouseId", min_length=1)
    available_quantity: Decimal = Field(alias="availableQuantity")
    reserved_quantity: Decimal = Field(alias="reservedQuantity")


class InventoryAvailabilityResult(ApiBaseModel):
    """Aggregated inventory availability for one part across warehouses."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", min_length=1)
    total_available_quantity: Decimal = Field(alias="totalAvailableQuantity")
    warehouses: list[WarehouseAvailabilityEntry] = Field(default_factory=list)



class FindAlternativeWarehousesParameters(ApiBaseModel):
    """Stable public input for findAlternativeWarehouses."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", strict=True, min_length=1)
    destination_warehouse_id: str = Field(alias="destinationWarehouseId", strict=True, min_length=1)
    required_quantity: Decimal = Field(alias="requiredQuantity", gt=0)
    required_by_date: date = Field(alias="requiredByDate")


class AlternativeWarehouseEstimator(ApiBaseModel):
    """Named transfer estimator assumptions returned with each candidate."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)


class AlternativeWarehouseEntry(ApiBaseModel):
    """One feasible source warehouse candidate for part transfer coverage."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    warehouse_id: str = Field(alias="warehouseId", min_length=1)
    warehouse_name: str = Field(alias="warehouseName", min_length=1)
    available_quantity: Decimal = Field(alias="availableQuantity")
    safety_stock_quantity: Decimal = Field(alias="safetyStockQuantity")
    committed_outgoing_transfer_quantity: Decimal = Field(alias="committedOutgoingTransferQuantity")
    transferable_quantity: Decimal = Field(alias="transferableQuantity")
    covered_quantity: Decimal = Field(alias="coveredQuantity")
    remaining_shortage: Decimal = Field(alias="remainingShortage")
    estimated_transfer_days: int = Field(alias="estimatedTransferDays", ge=0)
    estimated_arrival_date: date = Field(alias="estimatedArrivalDate")
    estimated_transfer_cost: Decimal = Field(alias="estimatedTransferCost")
    feasible: bool
    infeasibility_reasons: list[str] = Field(alias="infeasibilityReasons", default_factory=list)
    estimator: AlternativeWarehouseEstimator


class FindAlternativeWarehousesResult(ApiBaseModel):
    """Read-only alternative-warehouse result set."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    items: list[AlternativeWarehouseEntry] = Field(default_factory=list)
