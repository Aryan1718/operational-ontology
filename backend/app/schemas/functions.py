"""Pydantic schemas for ontology function execution."""

from __future__ import annotations

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


class GetInventoryAvailabilityParameters(ApiBaseModel):
    """Stable public input for getInventoryAvailability."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", strict=True, min_length=1)


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
