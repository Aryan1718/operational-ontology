"""Startup builder for the immutable ontology function handler registry."""

from __future__ import annotations

from app.functions.inventory import get_inventory_availability
from app.functions.registry import FunctionHandlerRegistry, RegisteredFunctionHandler
from app.schemas.functions import (
    GetInventoryAvailabilityParameters,
    InventoryAvailabilityItem,
)


def build_function_handler_registry() -> FunctionHandlerRegistry:
    """Build the immutable registry of executable ontology functions."""
    return FunctionHandlerRegistry(
        {
            "getInventoryAvailability": RegisteredFunctionHandler(
                handler_name="getInventoryAvailability",
                input_model=GetInventoryAvailabilityParameters,
                output_model=list[InventoryAvailabilityItem],
                execute=get_inventory_availability,
            )
        }
    )
