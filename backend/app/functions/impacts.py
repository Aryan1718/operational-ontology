"""Read-only impact-analysis function handlers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import InvalidOperation
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import select

from app.models.supply_chain import CustomerOrder, Shipment

from app.core.exceptions import ApplicationError
from app.functions.config import DEFAULT_ONTOLOGY_FUNCTION_CONFIG
from app.repositories.function_repository import (
    DemandProjectionRow,
    FunctionRepository,
    OpenOrderLineRow,
    ProductBomRequirementRow,
    PurchaseOrderSupplyRow,
    SupplierPartRow,
    WarehouseInventoryRow,
)
from app.runtime.function_engine import FunctionExecutionContext
from app.schemas.functions import (
    FindImpactedOrdersParameters,
    FindImpactedOrdersResult,
    FindImpactedPartsParameters,
    FindImpactedPartsResult,
    FindImpactedProductsParameters,
    FindImpactedProductsResult,
    ImpactedOrderEntry,
    ImpactedOrderProductEntry,
    ImpactedPartEntry,
    ImpactedProductEntry,
    MitigationRecommendationEntry,
    RankImpactedOrdersParameters,
    RankImpactedOrdersResult,
    RecommendMitigationPlanParameters,
    RecommendMitigationPlanResult,
    RankedImpactedOrderEntry,
    RankedOrderScoreBreakdown,
)

ZERO = Decimal("0.00")
DEFAULT_IMPACT_ANALYSIS_HORIZON_DAYS = 30
SUPPLIER_DELAY_RISK_TYPE = "supplier_delay"
CRITICALITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
ORDER_PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "critical": 3}
DESTINATION_WAREHOUSE_UNASSIGNED = "DESTINATION_WAREHOUSE_UNASSIGNED"
ONE_HUNDRED = Decimal("100")
ORDER_PRIORITY_SCORES = {"low": Decimal("25"), "normal": Decimal("50"), "high": Decimal("75"), "critical": Decimal("100")}
PART_CRITICALITY_SCORES = {"low": Decimal("25"), "medium": Decimal("50"), "high": Decimal("75"), "critical": Decimal("100")}



class RiskEventNotFoundError(ApplicationError):
    """Raised when a public risk-event identifier does not resolve."""

    def __init__(self, risk_event_id: str) -> None:
        super().__init__(
            code="RISK_EVENT_NOT_FOUND",
            message=f"Risk event '{risk_event_id}' was not found.",
            status_code=404,
            details={"riskEventId": risk_event_id},
        )


class UnsupportedRiskEventTypeError(ApplicationError):
    """Raised when the handler receives an unsupported risk type."""

    def __init__(self, risk_event_id: str, risk_type: str) -> None:
        super().__init__(
            code="UNSUPPORTED_RISK_EVENT_TYPE",
            message="The risk event type is not supported by this function.",
            status_code=422,
            details={"riskEventId": risk_event_id, "riskType": risk_type},
        )


class RiskEventSupplierNotFoundError(ApplicationError):
    """Raised when a supplier-delay event has no resolvable supplier."""

    def __init__(self, risk_event_id: str) -> None:
        super().__init__(
            code="RISK_EVENT_SUPPLIER_NOT_FOUND",
            message=f"Risk event '{risk_event_id}' does not reference a valid supplier.",
            status_code=404,
            details={"riskEventId": risk_event_id},
        )


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Shortage projection output for one part."""

    shortage_quantity: Decimal
    first_shortage_date: date | None


@dataclass(frozen=True, slots=True)
class PartProjection:
    """Baseline and delayed projections for one part."""

    part_id: UUID
    part_code: str
    part_name: str
    baseline_shortage_quantity: Decimal
    delayed_shortage_quantity: Decimal
    baseline_available_quantity: Decimal
    delayed_available_quantity: Decimal
    first_baseline_shortage_date: date | None
    first_delayed_shortage_date: date | None
    open_purchase_order_quantity: Decimal
    delayed_purchase_order_ids: list[str]


@dataclass(frozen=True, slots=True)
class ImpactedSupplierPartProjection:
    """Impacted supplier-linked part with supplier relation metadata."""

    supplier_part_id: str
    delay_days: int
    shortage_increase_quantity: Decimal
    projection: PartProjection


@dataclass(frozen=True, slots=True)
class SupplierDelayImpactState:
    """Shared supplier-delay projections reused across impact handlers."""

    repository: FunctionRepository
    supplier_id: UUID
    delay_days: int
    executed_at_date: date
    impacted_parts: list[ImpactedSupplierPartProjection]
    part_projections_by_id: dict[UUID, PartProjection]


@dataclass(frozen=True, slots=True)
class OrderLineAllocation:
    """Allocated fulfillable quantity for one order line in one scenario."""

    line: OpenOrderLineRow
    fulfillable_quantity: Decimal


@dataclass(frozen=True, slots=True)
class OrderImpactAggregate:
    """Mutable-looking values captured for one impacted order."""

    order_id: str
    order_number: str
    priority: str
    required_delivery_date: date
    destination_warehouse_id: str | None
    impacted_products: list[ImpactedOrderProductEntry]
    impacted_part_ids: list[str]
    required_quantity: Decimal
    baseline_fulfillable_quantity: Decimal
    delayed_fulfillable_quantity: Decimal
    shortage_quantity: Decimal
    shortage_ratio: Decimal
    baseline_projected_delay_days: int
    projected_delay_days: int
    estimated_order_value: Decimal
    risk_score: int
    impact_reason: str
    warnings: list[str]


def find_impacted_parts(
    context: FunctionExecutionContext,
    parameters: FindImpactedPartsParameters,
) -> FindImpactedPartsResult:
    """Return parts whose projected shortage worsens because of a supplier delay."""

    impact_state = _build_supplier_delay_impact_state(context, parameters.risk_event_id)

    items = [
        ImpactedPartEntry(
            partId=item.projection.part_code,
            partName=item.projection.part_name,
            supplierPartId=item.supplier_part_id,
            delayDays=item.delay_days,
            openPurchaseOrderQuantity=item.projection.open_purchase_order_quantity,
            baselineShortageQuantity=item.projection.baseline_shortage_quantity,
            delayedShortageQuantity=item.projection.delayed_shortage_quantity,
            shortageIncreaseQuantity=item.shortage_increase_quantity,
            firstBaselineShortageDate=item.projection.first_baseline_shortage_date,
            firstDelayedShortageDate=item.projection.first_delayed_shortage_date,
            delayedPurchaseOrderIds=item.projection.delayed_purchase_order_ids,
            impactReason=(
                f"Supplier delay increases projected shortage for {item.projection.part_code} "
                f"from {item.projection.baseline_shortage_quantity} to "
                f"{item.projection.delayed_shortage_quantity} within the impact horizon."
            ),
        )
        for item in impact_state.impacted_parts
    ]
    return FindImpactedPartsResult(items=items)


def find_impacted_products(
    context: FunctionExecutionContext,
    parameters: FindImpactedProductsParameters,
) -> FindImpactedProductsResult:
    """Return products whose maximum buildable quantity worsens because of a supplier delay."""

    impact_state = _build_supplier_delay_impact_state(context, parameters.risk_event_id)
    impacted_parts_by_id = {item.projection.part_id: item for item in impact_state.impacted_parts}
    candidate_rows = impact_state.repository.get_candidate_products_for_parts(set(impacted_parts_by_id))
    candidate_product_ids = {row.product_id for row in candidate_rows}
    if not candidate_product_ids:
        return FindImpactedProductsResult(items=[])

    bom_rows = impact_state.repository.get_active_product_bom_requirements(candidate_product_ids)
    bom_by_product = _group_bom_by_product(bom_rows)
    product_bom_part_ids = {row.part_id for row in bom_rows}
    part_projections_by_id = _build_part_projections(
        repository=impact_state.repository,
        part_ids=product_bom_part_ids,
        delayed_supplier_id=impact_state.supplier_id,
        delay_days=impact_state.delay_days,
        executed_at_date=impact_state.executed_at_date,
        part_metadata={row.part_id: (row.part_code, row.part_name) for row in bom_rows},
    )
    open_product_demands = {
        row.product_id: row.open_order_quantity
        for row in impact_state.repository.get_open_product_demands(candidate_product_ids)
    }

    items: list[ImpactedProductEntry] = []
    for product_id, product_bom in bom_by_product.items():
        if not product_bom:
            continue

        baseline_buildable, baseline_limiting_part_id = _calculate_maximum_buildable_quantity(
            product_bom,
            part_projections_by_id,
            scenario="baseline",
        )
        delayed_buildable, delayed_limiting_part_id = _calculate_maximum_buildable_quantity(
            product_bom,
            part_projections_by_id,
            scenario="delayed",
        )
        open_order_quantity = open_product_demands.get(product_id, ZERO)
        baseline_shortfall = max(ZERO, open_order_quantity - baseline_buildable)
        delayed_shortfall = max(ZERO, open_order_quantity - delayed_buildable)

        if delayed_buildable >= baseline_buildable and delayed_shortfall <= baseline_shortfall:
            continue

        impacted_part_ids = sorted(
            {
                row.part_code
                for row in product_bom
                if row.part_id in impacted_parts_by_id
            }
        )
        if not impacted_part_ids:
            continue

        highest_part_criticality = _select_highest_criticality(product_bom)
        limiting_part_id = delayed_limiting_part_id or baseline_limiting_part_id or product_bom[0].part_code
        items.append(
            ImpactedProductEntry(
                productId=product_bom[0].product_code,
                productName=product_bom[0].product_name,
                impactedPartIds=impacted_part_ids,
                requiredQuantities={row.part_code: row.quantity_required for row in product_bom},
                limitingPartId=limiting_part_id,
                baselineMaximumBuildableQuantity=baseline_buildable,
                delayedMaximumBuildableQuantity=delayed_buildable,
                openOrderQuantity=open_order_quantity,
                baselineProductionShortfallQuantity=baseline_shortfall,
                delayedProductionShortfallQuantity=delayed_shortfall,
                shortfallIncreaseQuantity=max(ZERO, delayed_shortfall - baseline_shortfall),
                highestPartCriticality=highest_part_criticality,
                productRiskLevel=highest_part_criticality,
                impactReason=(
                    f"Supplier delay reduces maximum buildable quantity for {product_bom[0].product_code} "
                    f"from {baseline_buildable} to {delayed_buildable}; limiting part {limiting_part_id}."
                ),
            )
        )

    items.sort(
        key=lambda item: (
            -item.shortfall_increase_quantity,
            -CRITICALITY_RANK.get(item.highest_part_criticality, -1),
            item.product_id,
        )
    )
    return FindImpactedProductsResult(items=items)


def find_impacted_orders(
    context: FunctionExecutionContext,
    parameters: FindImpactedOrdersParameters,
) -> FindImpactedOrdersResult:
    """Return open customer orders whose impacted-product fulfillment worsens."""

    impact_state = _build_supplier_delay_impact_state(context, parameters.risk_event_id)
    impacted_products_result = find_impacted_products(
        context,
        FindImpactedProductsParameters(riskEventId=parameters.risk_event_id),
    )
    impacted_products_by_code = {
        item.product_id: item
        for item in impacted_products_result.items
    }
    if not impacted_products_by_code:
        return FindImpactedOrdersResult(items=[])

    order_lines = impact_state.repository.get_open_order_lines_for_products(set(impacted_products_by_code))
    if not order_lines:
        return FindImpactedOrdersResult(items=[])

    order_lines_by_product: dict[str, list[OpenOrderLineRow]] = defaultdict(list)
    for row in order_lines:
        order_lines_by_product[row.product_code].append(row)

    order_aggregates: dict[UUID, dict[str, object]] = {}
    for product_code, product_definition in impacted_products_by_code.items():
        competing_lines = order_lines_by_product.get(product_code, [])
        if not competing_lines:
            continue

        sorted_lines = sorted(competing_lines, key=_order_line_allocation_sort_key)
        baseline_allocations = _allocate_product_quantity(
            sorted_lines,
            product_definition.baseline_maximum_buildable_quantity,
        )
        delayed_allocations = _allocate_product_quantity(
            sorted_lines,
            product_definition.delayed_maximum_buildable_quantity,
        )

        for line in sorted_lines:
            required_quantity = line.remaining_quantity
            baseline_fulfillable_quantity = baseline_allocations.get(line.order_line_id, ZERO)
            delayed_fulfillable_quantity = delayed_allocations.get(line.order_line_id, ZERO)
            baseline_shortage_quantity = max(ZERO, required_quantity - baseline_fulfillable_quantity)
            delayed_shortage_quantity = max(ZERO, required_quantity - delayed_fulfillable_quantity)
            delayed_delay_days = impact_state.delay_days if delayed_shortage_quantity > ZERO else 0
            baseline_delay_days = 0
            is_impacted = (
                delayed_fulfillable_quantity < baseline_fulfillable_quantity
                or delayed_shortage_quantity > baseline_shortage_quantity
                or delayed_delay_days > baseline_delay_days
            )
            if not is_impacted:
                continue

            aggregate = order_aggregates.setdefault(
                line.order_id,
                {
                    "orderId": line.order_code,
                    "orderNumber": line.order_code,
                    "priority": line.priority,
                    "requiredDeliveryDate": line.required_delivery_date,
                    "destinationWarehouseId": line.destination_warehouse_id,
                    "impactedProducts": [],
                    "impactedPartIds": set(),
                    "requiredQuantity": ZERO,
                    "baselineFulfillableQuantity": ZERO,
                    "delayedFulfillableQuantity": ZERO,
                    "baselineProjectedDelayDays": 0,
                    "projectedDelayDays": 0,
                    "estimatedOrderValue": ZERO,
                    "warnings": set(),
                },
            )

            aggregate["impactedProducts"].append(
                ImpactedOrderProductEntry(
                    productId=product_code,
                    requiredQuantity=required_quantity,
                    baselineFulfillableQuantity=baseline_fulfillable_quantity,
                    delayedFulfillableQuantity=delayed_fulfillable_quantity,
                    shortageQuantity=delayed_shortage_quantity,
                )
            )
            cast_impacted_parts = aggregate["impactedPartIds"]
            if isinstance(cast_impacted_parts, set):
                cast_impacted_parts.update(product_definition.impacted_part_ids)
            aggregate["requiredQuantity"] = aggregate["requiredQuantity"] + required_quantity
            aggregate["baselineFulfillableQuantity"] = aggregate["baselineFulfillableQuantity"] + baseline_fulfillable_quantity
            aggregate["delayedFulfillableQuantity"] = aggregate["delayedFulfillableQuantity"] + delayed_fulfillable_quantity
            aggregate["baselineProjectedDelayDays"] = max(aggregate["baselineProjectedDelayDays"], baseline_delay_days)
            aggregate["projectedDelayDays"] = max(aggregate["projectedDelayDays"], delayed_delay_days)
            aggregate["estimatedOrderValue"] = aggregate["estimatedOrderValue"] + line.estimated_line_value
            if aggregate["destinationWarehouseId"] is None and line.destination_warehouse_id is not None:
                aggregate["destinationWarehouseId"] = line.destination_warehouse_id
            warnings = aggregate["warnings"]
            if isinstance(warnings, set) and aggregate["destinationWarehouseId"] is None:
                warnings.add(DESTINATION_WAREHOUSE_UNASSIGNED)

    items: list[ImpactedOrderEntry] = []
    for aggregate in order_aggregates.values():
        required_quantity = aggregate["requiredQuantity"]
        delayed_fulfillable_quantity = aggregate["delayedFulfillableQuantity"]
        shortage_quantity = max(ZERO, required_quantity - delayed_fulfillable_quantity)
        if shortage_quantity <= ZERO and aggregate["projectedDelayDays"] <= aggregate["baselineProjectedDelayDays"]:
            continue
        shortage_ratio = _calculate_shortage_ratio(shortage_quantity, required_quantity)
        impacted_products = sorted(
            aggregate["impactedProducts"],
            key=lambda item: (item.product_id, item.required_quantity, item.shortage_quantity),
        )
        impacted_part_ids = sorted(aggregate["impactedPartIds"])
        items.append(
            ImpactedOrderEntry(
                orderId=aggregate["orderId"],
                orderNumber=aggregate["orderNumber"],
                priority=aggregate["priority"],
                requiredDeliveryDate=aggregate["requiredDeliveryDate"],
                destinationWarehouseId=aggregate["destinationWarehouseId"],
                impactedProducts=impacted_products,
                impactedPartIds=impacted_part_ids,
                requiredQuantity=required_quantity,
                baselineFulfillableQuantity=aggregate["baselineFulfillableQuantity"],
                delayedFulfillableQuantity=delayed_fulfillable_quantity,
                shortageQuantity=shortage_quantity,
                shortageRatio=shortage_ratio,
                baselineProjectedDelayDays=aggregate["baselineProjectedDelayDays"],
                projectedDelayDays=aggregate["projectedDelayDays"],
                estimatedOrderValue=aggregate["estimatedOrderValue"],
                riskScore=_calculate_minimal_order_risk_score(shortage_ratio),
                impactReason=(
                    f"Supplier delay reduces fulfillable quantity for order {aggregate['orderNumber']} "
                    f"across impacted products {', '.join(item.product_id for item in impacted_products)}."
                ),
                warnings=sorted(aggregate["warnings"]),
            )
        )

    items.sort(
        key=lambda item: (
            -ORDER_PRIORITY_RANK.get(item.priority, -1),
            item.required_delivery_date,
            -item.shortage_quantity,
            item.order_id,
        )
    )
    return FindImpactedOrdersResult(items=items)


def rank_impacted_orders(
    context: FunctionExecutionContext,
    parameters: RankImpactedOrdersParameters,
) -> RankImpactedOrdersResult:
    """Rank impacted orders returned by the existing impact analysis."""

    impacted_orders = find_impacted_orders(
        context,
        FindImpactedOrdersParameters(riskEventId=parameters.risk_event_id),
    )
    if not impacted_orders.items:
        return RankImpactedOrdersResult(items=[])

    repository = FunctionRepository(context.session)
    product_codes = {
        impacted_product.product_id
        for order in impacted_orders.items
        for impacted_product in order.impacted_products
    }
    order_lines = repository.get_open_order_lines_for_products(product_codes)
    order_date_by_code: dict[str, date] = {}
    product_ids_by_code: dict[str, UUID] = {}
    for line in order_lines:
        current_order_date = order_date_by_code.get(line.order_code)
        if current_order_date is None or line.order_date < current_order_date:
            order_date_by_code[line.order_code] = line.order_date
        product_ids_by_code.setdefault(line.product_code, line.product_id)

    bom_rows = repository.get_active_product_bom_requirements(set(product_ids_by_code.values()))
    criticality_by_product_code: dict[str, dict[str, str]] = defaultdict(dict)
    for row in bom_rows:
        criticality_by_product_code[row.product_code][row.part_code] = row.part_criticality

    ranked_items: list[tuple[RankedImpactedOrderEntry, date]] = []
    for order in impacted_orders.items:
        warnings = set(order.warnings)
        highest_part_criticality = None
        for part_code in order.impacted_part_ids:
            for product in order.impacted_products:
                criticality = criticality_by_product_code.get(product.product_id, {}).get(part_code)
                if criticality is None:
                    continue
                if highest_part_criticality is None or CRITICALITY_RANK.get(criticality, -1) > CRITICALITY_RANK.get(highest_part_criticality, -1):
                    highest_part_criticality = criticality
        if highest_part_criticality is None:
            highest_part_criticality = "low"
            warnings.add("PART_CRITICALITY_DEFAULTED")

        breakdown = RankedOrderScoreBreakdown(
            orderPriority=ORDER_PRIORITY_SCORES.get(order.priority, Decimal("50")),
            deliveryUrgency=_calculate_delivery_urgency_score(context.executed_at.date(), order.required_delivery_date),
            shortageRatio=_clamp(order.shortage_ratio * ONE_HUNDRED, ZERO, ONE_HUNDRED),
            projectedDelay=_calculate_projected_delay_score(order.projected_delay_days),
            orderValue=_calculate_order_value_score(order.estimated_order_value),
            partCriticality=PART_CRITICALITY_SCORES.get(highest_part_criticality, Decimal("25")),
        )
        weights = DEFAULT_ONTOLOGY_FUNCTION_CONFIG.order_ranking_weights
        weighted_total = (
            breakdown.order_priority * weights.order_priority
            + breakdown.delivery_urgency * weights.delivery_urgency
            + breakdown.shortage_ratio * weights.shortage_ratio
            + breakdown.projected_delay * weights.projected_delay
            + breakdown.order_value * weights.order_value
            + breakdown.part_criticality * weights.part_criticality
        )
        risk_score = int(_clamp(weighted_total, ZERO, ONE_HUNDRED).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        explanation = _build_ranking_explanation(
            priority=order.priority,
            recommended_attention=_map_recommended_attention(risk_score),
            breakdown=breakdown,
        )
        ranked_items.append(
            (
                RankedImpactedOrderEntry(
                    rank=0,
                    orderId=order.order_id,
                    orderNumber=order.order_number,
                    riskScore=risk_score,
                    scoreBreakdown=breakdown,
                    shortageQuantity=order.shortage_quantity,
                    projectedDelayDays=order.projected_delay_days,
                    estimatedOrderValue=order.estimated_order_value,
                    recommendedAttention=_map_recommended_attention(risk_score),
                    rankingExplanation=explanation if not warnings else f"{explanation} Warnings: {', '.join(sorted(warnings))}.",
                ),
                order_date_by_code.get(order.order_id, date.max),
            )
        )

    ranked_items.sort(
        key=lambda item: (
            -item[0].risk_score,
            next(order.required_delivery_date for order in impacted_orders.items if order.order_id == item[0].order_id),
            -item[0].shortage_quantity,
            -item[0].estimated_order_value,
            item[1],
            item[0].order_id,
        )
    )

    results: list[RankedImpactedOrderEntry] = []
    for index, (item, _order_date) in enumerate(ranked_items, start=1):
        results.append(item.model_copy(update={"rank": index}))
    return RankImpactedOrdersResult(items=results)


def _build_supplier_delay_impact_state(
    context: FunctionExecutionContext,
    risk_event_id: str,
) -> SupplierDelayImpactState:
    repository = FunctionRepository(context.session)
    risk_event = repository.get_risk_event_by_code(risk_event_id)
    if risk_event is None:
        raise RiskEventNotFoundError(risk_event_id)
    if risk_event.risk_type != SUPPLIER_DELAY_RISK_TYPE:
        raise UnsupportedRiskEventTypeError(risk_event_id, risk_event.risk_type)
    if risk_event.supplier_id is None or not repository.supplier_exists(risk_event.supplier_id):
        raise RiskEventSupplierNotFoundError(risk_event_id)

    supplier_parts = repository.get_active_supplier_parts(risk_event.supplier_id)
    part_ids = {row.part_id for row in supplier_parts}
    part_projections_by_id = _build_part_projections(
        repository=repository,
        part_ids=part_ids,
        delayed_supplier_id=risk_event.supplier_id,
        delay_days=max(0, risk_event.delay_days or 0),
        executed_at_date=context.executed_at.date(),
        part_metadata={
            supplier_part.part_id: (supplier_part.part_code, supplier_part.part_name)
            for supplier_part in supplier_parts
        },
    )

    impacted_parts: list[ImpactedSupplierPartProjection] = []
    for supplier_part in supplier_parts:
        projection = part_projections_by_id[supplier_part.part_id]
        shortage_increase_quantity = (
            projection.delayed_shortage_quantity - projection.baseline_shortage_quantity
        )
        if shortage_increase_quantity <= ZERO:
            continue
        impacted_parts.append(
            ImpactedSupplierPartProjection(
                supplier_part_id=supplier_part.supplier_part_id,
                delay_days=max(0, risk_event.delay_days or 0),
                shortage_increase_quantity=shortage_increase_quantity,
                projection=projection,
            )
        )

    impacted_parts.sort(
        key=lambda item: (
            -item.shortage_increase_quantity,
            item.projection.first_delayed_shortage_date or date.max,
            item.projection.part_code,
        )
    )
    return SupplierDelayImpactState(
        repository=repository,
        supplier_id=risk_event.supplier_id,
        delay_days=max(0, risk_event.delay_days or 0),
        executed_at_date=context.executed_at.date(),
        impacted_parts=impacted_parts,
        part_projections_by_id=part_projections_by_id,
    )


def _build_part_projections(
    *,
    repository: FunctionRepository,
    part_ids: set[UUID],
    delayed_supplier_id: UUID,
    delay_days: int,
    executed_at_date: date,
    part_metadata: dict[UUID, tuple[str, str]],
) -> dict[UUID, PartProjection]:
    if not part_ids:
        return {}

    purchase_orders = repository.get_open_purchase_orders_for_parts(part_ids)
    demands = repository.get_open_part_demands(part_ids)
    horizon_date = _resolve_horizon_date(executed_at_date, demands)
    purchase_orders_by_part = _group_purchase_orders_by_part(purchase_orders)
    demands_by_part = _group_demands_by_part(demands, horizon_date=horizon_date)
    demand_warehouses = {row.warehouse_code for rows in demands_by_part.values() for row in rows}
    inventory_rows = repository.get_inventory_for_part_warehouses(part_ids, demand_warehouses)
    inventory_by_part = _group_inventory_by_part(inventory_rows)
    projections: dict[UUID, PartProjection] = {}
    for part_id in part_ids:
        purchase_order_rows = purchase_orders_by_part.get(part_id, [])
        demand_rows = demands_by_part.get(part_id, [])
        part_code, part_name = part_metadata.get(part_id, (str(part_id), str(part_id)))
        open_purchase_order_quantity = sum((row.open_quantity for row in purchase_order_rows), start=ZERO)
        baseline_projection = _project_shortage(
            starting_available=inventory_by_part.get(part_id, ZERO),
            demands=demand_rows,
            inbound=_build_inbound_schedule(purchase_order_rows, delayed_supplier_id, 0, horizon_date),
        )
        delayed_projection = _project_shortage(
            starting_available=inventory_by_part.get(part_id, ZERO),
            demands=demand_rows,
            inbound=_build_inbound_schedule(purchase_order_rows, delayed_supplier_id, delay_days, horizon_date),
        )
        projections[part_id] = PartProjection(
            part_id=part_id,
            part_code=part_code,
            part_name=part_name,
            baseline_shortage_quantity=baseline_projection.shortage_quantity,
            delayed_shortage_quantity=delayed_projection.shortage_quantity,
            baseline_available_quantity=max(
                ZERO,
                inventory_by_part.get(part_id, ZERO) + open_purchase_order_quantity - baseline_projection.shortage_quantity,
            ),
            delayed_available_quantity=max(
                ZERO,
                inventory_by_part.get(part_id, ZERO) + open_purchase_order_quantity - delayed_projection.shortage_quantity,
            ),
            first_baseline_shortage_date=baseline_projection.first_shortage_date,
            first_delayed_shortage_date=delayed_projection.first_shortage_date,
            open_purchase_order_quantity=open_purchase_order_quantity,
            delayed_purchase_order_ids=sorted(
                {row.purchase_order_id for row in purchase_order_rows if row.supplier_id == delayed_supplier_id}
            ),
        )

    return projections


def _resolve_horizon_date(executed_at_date: date, demands: list[DemandProjectionRow]) -> date:
    max_horizon_date = executed_at_date + timedelta(days=DEFAULT_IMPACT_ANALYSIS_HORIZON_DAYS)
    if not demands:
        return max_horizon_date
    latest_required_date = max(row.required_date for row in demands)
    return min(latest_required_date, max_horizon_date)


def _group_purchase_orders_by_part(
    rows: list[PurchaseOrderSupplyRow],
) -> dict[UUID, list[PurchaseOrderSupplyRow]]:
    grouped: dict[UUID, list[PurchaseOrderSupplyRow]] = defaultdict(list)
    for row in rows:
        grouped[row.part_id].append(row)
    return dict(grouped)


def _group_demands_by_part(
    rows: list[DemandProjectionRow],
    *,
    horizon_date: date,
) -> dict[UUID, list[DemandProjectionRow]]:
    grouped: dict[UUID, list[DemandProjectionRow]] = defaultdict(list)
    for row in rows:
        if row.required_date <= horizon_date:
            grouped[row.part_id].append(row)
    return dict(grouped)


def _group_inventory_by_part(
    rows: list[WarehouseInventoryRow],
) -> dict[UUID, Decimal]:
    grouped: dict[UUID, Decimal] = defaultdict(lambda: ZERO)
    for row in rows:
        grouped[row.part_id] += row.available_quantity
    return dict(grouped)


def _group_bom_by_product(
    rows: list[ProductBomRequirementRow],
) -> dict[UUID, list[ProductBomRequirementRow]]:
    grouped: dict[UUID, list[ProductBomRequirementRow]] = defaultdict(list)
    for row in rows:
        grouped[row.product_id].append(row)
    return dict(grouped)


def _build_inbound_schedule(
    purchase_orders: list[PurchaseOrderSupplyRow],
    delayed_supplier_id: UUID,
    delay_days: int,
    horizon_date: date,
) -> dict[date, Decimal]:
    inbound_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for row in purchase_orders:
        if row.expected_delivery_date is None:
            continue
        projected_date = row.expected_delivery_date + timedelta(
            days=delay_days if row.supplier_id == delayed_supplier_id else 0
        )
        if projected_date <= horizon_date:
            inbound_by_date[projected_date] += row.open_quantity
    return dict(inbound_by_date)


def _project_shortage(
    *,
    starting_available: Decimal,
    demands: list[DemandProjectionRow],
    inbound: dict[date, Decimal],
) -> ProjectionResult:
    available = starting_available
    first_shortage_date: date | None = None
    demand_by_date: dict[date, Decimal] = defaultdict(lambda: ZERO)
    for row in demands:
        demand_by_date[row.required_date] += row.demand_quantity

    for current_date in sorted(set(demand_by_date) | set(inbound)):
        available += inbound.get(current_date, ZERO)
        available -= demand_by_date.get(current_date, ZERO)
        if available < ZERO and first_shortage_date is None:
            first_shortage_date = current_date

    return ProjectionResult(
        shortage_quantity=max(ZERO, -available),
        first_shortage_date=first_shortage_date,
    )


def _calculate_maximum_buildable_quantity(
    product_bom: list[ProductBomRequirementRow],
    part_projections_by_id: dict[UUID, PartProjection],
    *,
    scenario: str,
) -> tuple[Decimal, str | None]:
    buildable_quantities: list[tuple[Decimal, str]] = []
    for requirement in product_bom:
        part_projection = part_projections_by_id.get(requirement.part_id)
        projected_available = ZERO
        if part_projection is not None:
            projected_available = (
                part_projection.baseline_available_quantity
                if scenario == "baseline"
                else part_projection.delayed_available_quantity
            )

        buildable_quantities.append(
            (
                _floor_buildable_quantity(projected_available, requirement.quantity_required),
                requirement.part_code,
            )
        )

    if not buildable_quantities:
        return ZERO, None

    buildable_quantities.sort(key=lambda item: (item[0], item[1]))
    return buildable_quantities[0]


def _floor_buildable_quantity(
    projected_available_part_quantity: Decimal,
    quantity_required_per_product: Decimal,
) -> Decimal:
    if quantity_required_per_product <= ZERO:
        return ZERO
    return (projected_available_part_quantity / quantity_required_per_product).quantize(
        Decimal("1"),
        rounding=ROUND_FLOOR,
    )


def _select_highest_criticality(product_bom: list[ProductBomRequirementRow]) -> str:
    highest = "low"
    for row in product_bom:
        if CRITICALITY_RANK.get(row.part_criticality, -1) > CRITICALITY_RANK.get(highest, -1):
            highest = row.part_criticality
    return highest


def _order_line_allocation_sort_key(line: OpenOrderLineRow) -> tuple[int, date, date, str]:
    return (
        -ORDER_PRIORITY_RANK.get(line.priority, -1),
        line.required_delivery_date,
        line.order_date,
        line.order_code,
    )



def _allocate_product_quantity(
    lines: list[OpenOrderLineRow],
    available_quantity: Decimal,
) -> dict[UUID, Decimal]:
    remaining_available = max(ZERO, available_quantity)
    allocations: dict[UUID, Decimal] = {}
    for line in lines:
        if remaining_available <= ZERO:
            allocations[line.order_line_id] = ZERO
            continue
        fulfillable_quantity = min(line.remaining_quantity, remaining_available)
        allocations[line.order_line_id] = fulfillable_quantity
        remaining_available -= fulfillable_quantity
    return allocations



def _calculate_delivery_urgency_score(executed_at_date: date, required_delivery_date: date) -> Decimal:
    days_until_delivery = (required_delivery_date - executed_at_date).days
    if days_until_delivery <= 0:
        return Decimal("100")
    if days_until_delivery <= 2:
        return Decimal("90")
    if days_until_delivery <= 5:
        return Decimal("75")
    if days_until_delivery <= 10:
        return Decimal("50")
    if days_until_delivery <= 20:
        return Decimal("25")
    return Decimal("10")


def _calculate_projected_delay_score(projected_delay_days: int) -> Decimal:
    maximum_days = DEFAULT_ONTOLOGY_FUNCTION_CONFIG.maximum_projected_delay_score_days
    if maximum_days <= ZERO:
        return ZERO
    return _clamp((Decimal(projected_delay_days) / maximum_days) * ONE_HUNDRED, ZERO, ONE_HUNDRED)


def _calculate_order_value_score(estimated_order_value: Decimal) -> Decimal:
    if estimated_order_value < Decimal("5000"):
        return Decimal("20")
    if estimated_order_value < Decimal("20000"):
        return Decimal("40")
    if estimated_order_value < Decimal("50000"):
        return Decimal("60")
    if estimated_order_value < Decimal("100000"):
        return Decimal("80")
    return Decimal("100")


def _map_recommended_attention(risk_score: int) -> str:
    if risk_score <= 24:
        return "monitor"
    if risk_score <= 49:
        return "review"
    if risk_score <= 74:
        return "urgent"
    return "immediate"


def _build_ranking_explanation(
    *,
    priority: str,
    recommended_attention: str,
    breakdown: RankedOrderScoreBreakdown,
) -> str:
    factors = [
        ("order priority", breakdown.order_priority),
        ("delivery urgency", breakdown.delivery_urgency),
        ("shortage ratio", breakdown.shortage_ratio),
        ("projected delay", breakdown.projected_delay),
        ("order value", breakdown.order_value),
        ("part criticality", breakdown.part_criticality),
    ]
    factors.sort(key=lambda item: (-item[1], item[0]))
    strongest = ", ".join(name for name, _score in factors[:2])
    return f"Recommended attention is {recommended_attention} because the strongest factors are {strongest} for a {priority} priority order."


def _clamp(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
    return max(minimum, min(maximum, value))


def _calculate_shortage_ratio(shortage_quantity: Decimal, required_quantity: Decimal) -> Decimal:
    if required_quantity <= ZERO:
        return ZERO
    return shortage_quantity / required_quantity



def _calculate_minimal_order_risk_score(shortage_ratio: Decimal) -> int:
    normalized_ratio = min(Decimal("1.00"), max(ZERO, shortage_ratio))
    return int((normalized_ratio * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))



MONEY_QUANTUM = Decimal("0.01")
CONFIDENCE_QUANTUM = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class PartShortageRequirement:
    order_id: str
    order_number: str
    part_id: str
    destination_warehouse_id: str | None
    required_by_date: date
    shortage_quantity: Decimal
    order_shortage_quantity: Decimal
    estimated_order_value: Decimal



def recommend_mitigation_plan(
    context: FunctionExecutionContext,
    parameters: RecommendMitigationPlanParameters,
) -> RecommendMitigationPlanResult:
    """Recommend a deterministic, read-only mitigation strategy for a risk event."""

    from app.functions.inventory import (
        calculate_stockout_risk,
        find_alternative_warehouses,
        find_expeditable_purchase_orders,
    )
    from app.schemas.functions import (
        CalculateStockoutRiskParameters,
        FindAlternativeWarehousesParameters,
        FindExpeditablePurchaseOrdersParameters,
    )

    impact_state = _build_supplier_delay_impact_state(context, parameters.risk_event_id)
    impacted_orders = find_impacted_orders(context, FindImpactedOrdersParameters(riskEventId=parameters.risk_event_id))
    ranked_orders = rank_impacted_orders(context, RankImpactedOrdersParameters(riskEventId=parameters.risk_event_id))

    ranked_order_ids = [item.order_id for item in ranked_orders.items]
    impacted_order_map = {item.order_id: item for item in impacted_orders.items}
    ordered_impacted_orders = [impacted_order_map[order_id] for order_id in ranked_order_ids if order_id in impacted_order_map]
    if not ordered_impacted_orders:
        return RecommendMitigationPlanResult(
            riskEventId=parameters.risk_event_id,
            recommendedStrategy="MANUAL_INTERVENTION",
            priority="LOW",
            confidenceScore=Decimal("1.00"),
            affectedOrderIds=[],
            recommendations=[],
            unresolvedShortageQuantity=ZERO,
            explanation="The risk event exists, but no impacted customer orders were found in the current read-only snapshot.",
        )

    impacted_products = find_impacted_products(context, FindImpactedProductsParameters(riskEventId=parameters.risk_event_id))
    product_requirements = {product.product_id: product.required_quantities for product in impacted_products.items}
    part_shortages = _build_part_shortage_requirements(ordered_impacted_orders, product_requirements)

    recommendations: list[MitigationRecommendationEntry] = []
    transfer_claims: dict[tuple[str, str], Decimal] = {}
    expedite_claims: dict[str, Decimal] = {}
    total_shortage = sum((requirement.shortage_quantity for requirement in part_shortages), start=ZERO)
    unresolved_shortage = total_shortage
    transfer_covered = ZERO
    expedite_covered = ZERO

    supplier_code = _resolve_supplier_code(context, impact_state.supplier_id)

    for requirement in part_shortages:
        latest_arrival_date = requirement.required_by_date
        if requirement.destination_warehouse_id is not None:
            stockout_risk = calculate_stockout_risk(
                context,
                CalculateStockoutRiskParameters(
                    partId=requirement.part_id,
                    warehouseId=requirement.destination_warehouse_id,
                    horizonDate=requirement.required_by_date,
                ),
            )
            if stockout_risk.stockout_date is not None:
                latest_arrival_date = min(latest_arrival_date, stockout_risk.stockout_date)

        remaining_requirement = requirement.shortage_quantity
        best_transfer = None
        if requirement.destination_warehouse_id is not None:
            transfer_candidates = find_alternative_warehouses(
                context,
                FindAlternativeWarehousesParameters(
                    partId=requirement.part_id,
                    destinationWarehouseId=requirement.destination_warehouse_id,
                    requiredQuantity=requirement.shortage_quantity,
                    requiredByDate=requirement.required_by_date,
                ),
            )
            viable_transfers = []
            for candidate in transfer_candidates.items:
                available = candidate.transferable_quantity - transfer_claims.get((candidate.warehouse_id, requirement.part_id), ZERO)
                if available <= ZERO or candidate.estimated_arrival_date > latest_arrival_date:
                    continue
                covered_quantity = min(remaining_requirement, available)
                viable_transfers.append((candidate, covered_quantity))
            viable_transfers.sort(
                key=lambda item: (
                    -item[1],
                    item[0].estimated_arrival_date,
                    item[0].warehouse_id,
                )
            )
            if viable_transfers:
                best_transfer = viable_transfers[0]

        best_expedite = None
        expedite_candidates = find_expeditable_purchase_orders(
            context,
            FindExpeditablePurchaseOrdersParameters(
                partId=requirement.part_id,
                supplierId=supplier_code,
                requiredByDate=requirement.required_by_date,
            ),
        )
        viable_expedites = []
        for candidate in expedite_candidates.items:
            if not candidate.feasible or candidate.possible_expedited_date > latest_arrival_date:
                continue
            available = candidate.open_quantity - expedite_claims.get(candidate.purchase_order_id, ZERO)
            if available <= ZERO:
                continue
            covered_quantity = min(remaining_requirement, available)
            viable_expedites.append((candidate, covered_quantity))
        viable_expedites.sort(
            key=lambda item: (
                -item[1],
                item[0].possible_expedited_date,
                item[0].purchase_order_id,
            )
        )
        if viable_expedites:
            best_expedite = viable_expedites[0]

        if best_transfer is not None and best_transfer[1] >= remaining_requirement:
            candidate, covered_quantity = best_transfer
            transfer_claims[(candidate.warehouse_id, requirement.part_id)] = transfer_claims.get((candidate.warehouse_id, requirement.part_id), ZERO) + covered_quantity
            transfer_covered += covered_quantity
            unresolved_shortage -= covered_quantity
            recommendations.append(
                MitigationRecommendationEntry(
                    type="REALLOCATE_INVENTORY",
                    partId=requirement.part_id,
                    sourceWarehouseId=candidate.warehouse_id,
                    destinationWarehouseId=requirement.destination_warehouse_id,
                    quantity=covered_quantity,
                    expectedArrivalDate=candidate.estimated_arrival_date,
                    reason="Available inventory can arrive before the projected stockout or required fulfillment date.",
                )
            )
            continue

        if best_transfer is not None and best_transfer[1] > ZERO:
            candidate, covered_quantity = best_transfer
            transfer_claims[(candidate.warehouse_id, requirement.part_id)] = transfer_claims.get((candidate.warehouse_id, requirement.part_id), ZERO) + covered_quantity
            transfer_covered += covered_quantity
            unresolved_shortage -= covered_quantity
            remaining_requirement -= covered_quantity
            recommendations.append(
                MitigationRecommendationEntry(
                    type="REALLOCATE_INVENTORY",
                    partId=requirement.part_id,
                    sourceWarehouseId=candidate.warehouse_id,
                    destinationWarehouseId=requirement.destination_warehouse_id,
                    quantity=covered_quantity,
                    expectedArrivalDate=candidate.estimated_arrival_date,
                    reason="Alternative inventory covers part of the shortage before the projected stockout or required fulfillment date.",
                )
            )

        if best_expedite is not None and best_expedite[1] > ZERO:
            candidate, covered_quantity = best_expedite
            usable_quantity = min(remaining_requirement, covered_quantity)
            expedite_claims[candidate.purchase_order_id] = expedite_claims.get(candidate.purchase_order_id, ZERO) + usable_quantity
            expedite_covered += usable_quantity
            unresolved_shortage -= usable_quantity
            recommendations.append(
                MitigationRecommendationEntry(
                    type="EXPEDITE_PURCHASE_ORDER",
                    partId=requirement.part_id,
                    destinationWarehouseId=candidate.destination_warehouse_id or requirement.destination_warehouse_id,
                    purchaseOrderId=candidate.purchase_order_id,
                    quantity=usable_quantity,
                    expectedArrivalDate=candidate.possible_expedited_date,
                    reason="Expediting the purchase order can recover shortage quantity before the projected stockout or required fulfillment date.",
                )
            )

    unresolved_shortage = max(ZERO, unresolved_shortage.quantize(MONEY_QUANTUM))
    transfer_covered = transfer_covered.quantize(MONEY_QUANTUM)
    expedite_covered = expedite_covered.quantize(MONEY_QUANTUM)

    if total_shortage <= ZERO:
        recommended_strategy = "MANUAL_INTERVENTION"
    elif transfer_covered >= total_shortage and transfer_covered > ZERO:
        recommended_strategy = "REALLOCATE_INVENTORY"
    elif transfer_covered <= ZERO and expedite_covered >= total_shortage and expedite_covered > ZERO:
        recommended_strategy = "EXPEDITE_PURCHASE_ORDER"
    elif transfer_covered > ZERO and expedite_covered > ZERO:
        recommended_strategy = "COMBINED_MITIGATION"
    else:
        recommended_strategy = "MANUAL_INTERVENTION"

    priority = ordered_impacted_orders[0].priority.upper()
    confidence_score = _calculate_plan_confidence(
        ordered_impacted_orders=ordered_impacted_orders,
        total_shortage=total_shortage,
        unresolved_shortage=unresolved_shortage,
        recommendation_count=len(recommendations),
        recommended_strategy=recommended_strategy,
    )
    explanation = _build_mitigation_explanation(
        recommended_strategy=recommended_strategy,
        transfer_covered=transfer_covered,
        expedite_covered=expedite_covered,
        unresolved_shortage=unresolved_shortage,
        affected_order_ids=ranked_order_ids,
    )

    return RecommendMitigationPlanResult(
        riskEventId=parameters.risk_event_id,
        recommendedStrategy=recommended_strategy,
        priority=priority,
        confidenceScore=confidence_score,
        affectedOrderIds=ranked_order_ids,
        recommendations=recommendations,
        unresolvedShortageQuantity=unresolved_shortage,
        explanation=explanation,
    )



def _resolve_supplier_code(context: FunctionExecutionContext, supplier_id: UUID) -> str | None:
    from app.models.supply_chain import Supplier

    supplier = context.session.get(Supplier, supplier_id)
    return supplier.supplier_code if supplier is not None else None



def _calculate_plan_confidence(*, ordered_impacted_orders, total_shortage, unresolved_shortage, recommendation_count, recommended_strategy):
    coverage_ratio = Decimal("1.00") if total_shortage <= ZERO else _clamp((total_shortage - unresolved_shortage) / total_shortage, ZERO, Decimal("1.00"))
    destination_ratio = _safe_ratio(sum(1 for order in ordered_impacted_orders if order.destination_warehouse_id is not None), len(ordered_impacted_orders))
    recommendation_ratio = Decimal("0.20") if recommendation_count <= 0 else Decimal("1.00")
    strategy_adjustment = {
        "REALLOCATE_INVENTORY": Decimal("0.00"),
        "EXPEDITE_PURCHASE_ORDER": Decimal("-0.03"),
        "COMBINED_MITIGATION": Decimal("-0.05"),
        "MANUAL_INTERVENTION": Decimal("-0.10"),
    }.get(recommended_strategy, Decimal("-0.10"))
    confidence = Decimal("0.35") + (coverage_ratio * Decimal("0.40")) + (destination_ratio * Decimal("0.15")) + (recommendation_ratio * Decimal("0.15")) + strategy_adjustment
    return _clamp(confidence, ZERO, Decimal("1.00")).quantize(CONFIDENCE_QUANTUM)



def _build_mitigation_explanation(*, recommended_strategy, transfer_covered, expedite_covered, unresolved_shortage, affected_order_ids):
    affected_orders = ", ".join(affected_order_ids) if affected_order_ids else "no affected orders"
    if recommended_strategy == "REALLOCATE_INVENTORY":
        return f"Reallocating {transfer_covered} units covers the projected shortage for affected orders {affected_orders} before the required dates."
    if recommended_strategy == "EXPEDITE_PURCHASE_ORDER":
        return f"Expediting inbound supply for {expedite_covered} units is the earliest deterministic way to protect affected orders {affected_orders}."
    if recommended_strategy == "COMBINED_MITIGATION":
        return f"Reallocating {transfer_covered} units and expediting {expedite_covered} units leaves {unresolved_shortage} units unresolved across affected orders {affected_orders}."
    return f"Neither alternative inventory nor expeditable purchase orders fully prevent the shortage; {unresolved_shortage} units remain unresolved for affected orders {affected_orders}."



def _build_part_shortage_requirements(orders, product_requirements):
    requirements = []
    for order in orders:
        shortages_by_part = defaultdict(lambda: ZERO)
        for impacted_product in order.impacted_products:
            quantity_map = product_requirements.get(impacted_product.product_id, {})
            for part_id, quantity_required in quantity_map.items():
                shortages_by_part[part_id] += impacted_product.shortage_quantity * quantity_required
        for part_id, shortage_quantity in sorted(shortages_by_part.items()):
            if shortage_quantity <= ZERO:
                continue
            requirements.append(PartShortageRequirement(order.order_id, order.order_number, part_id, order.destination_warehouse_id, order.required_delivery_date, shortage_quantity, order.shortage_quantity, order.estimated_order_value))
    return requirements

def _safe_ratio(numerator, denominator):
    if denominator <= 0:
        return Decimal("1.00")
    return Decimal(numerator) / Decimal(denominator)


def _decimal_ratio(numerator, denominator):
    if denominator <= ZERO:
        return Decimal("1.00")
    try:
        return _clamp(numerator / denominator, ZERO, Decimal("1.00"))
    except InvalidOperation:
        return ZERO
