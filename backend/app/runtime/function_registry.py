"""Startup builder for the immutable ontology function handler registry."""

from __future__ import annotations

from app.functions.impacts import (
    find_impacted_orders,
    find_impacted_parts,
    find_impacted_products,
)
from app.functions.inventory import (
    calculate_stockout_risk,
    find_alternative_warehouses,
    get_inventory_availability,
)
from app.functions.registry import FunctionHandlerRegistry, RegisteredFunctionHandler
from app.schemas.functions import (
    CalculateStockoutRiskParameters,
    CalculateStockoutRiskResult,
    FindImpactedOrdersParameters,
    FindImpactedOrdersResult,
    FindImpactedPartsParameters,
    FindImpactedPartsResult,
    FindAlternativeWarehousesParameters,
    FindAlternativeWarehousesResult,
    FindImpactedProductsParameters,
    FindImpactedProductsResult,
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityResult,
)


def build_function_handler_registry() -> FunctionHandlerRegistry:
    """Build the immutable registry of executable ontology functions."""
    return FunctionHandlerRegistry(
        {
            "findImpactedParts": RegisteredFunctionHandler(
                handler_name="findImpactedParts",
                input_model=FindImpactedPartsParameters,
                output_model=FindImpactedPartsResult,
                execute=find_impacted_parts,
            ),
            "findImpactedProducts": RegisteredFunctionHandler(
                handler_name="findImpactedProducts",
                input_model=FindImpactedProductsParameters,
                output_model=FindImpactedProductsResult,
                execute=find_impacted_products,
            ),
            "findImpactedOrders": RegisteredFunctionHandler(
                handler_name="findImpactedOrders",
                input_model=FindImpactedOrdersParameters,
                output_model=FindImpactedOrdersResult,
                execute=find_impacted_orders,
            ),
            "calculateStockoutRisk": RegisteredFunctionHandler(
                handler_name="calculateStockoutRisk",
                input_model=CalculateStockoutRiskParameters,
                output_model=CalculateStockoutRiskResult,
                execute=calculate_stockout_risk,
            ),
            "getInventoryAvailability": RegisteredFunctionHandler(
                handler_name="getInventoryAvailability",
                input_model=GetInventoryAvailabilityParameters,
                output_model=InventoryAvailabilityResult,
                execute=get_inventory_availability,
            ),
            "findAlternativeWarehouses": RegisteredFunctionHandler(
                handler_name="findAlternativeWarehouses",
                input_model=FindAlternativeWarehousesParameters,
                output_model=FindAlternativeWarehousesResult,
                execute=find_alternative_warehouses,
            ),
        }
    )
