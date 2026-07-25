"""Pydantic schemas for ontology function execution."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field

from app.schemas.common import ApiBaseModel


class FunctionRequest(ApiBaseModel):
    """Strict generic request body for public ontology function execution."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    parameters: dict[str, Any] = Field(default_factory=dict)


class FunctionExecutionResponse(ApiBaseModel):
    """Shared successful payload returned from the Function Engine."""

    function_name: str = Field(alias="functionName")
    result: Any
    warnings: list[str] = Field(default_factory=list)


class GetInventoryAvailabilityParameters(ApiBaseModel):
    """Stable public input for getInventoryAvailability."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    part_id: str = Field(alias="partId", min_length=1)
    warehouse_id: str | None = Field(default=None, alias="warehouseId")
    required_by_date: date | None = Field(default=None, alias="requiredByDate")


class InventoryAvailabilityItem(ApiBaseModel):
    """Validated public inventory availability row."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    warehouse_id: str = Field(alias="warehouseId")
    warehouse_name: str | None = Field(default=None, alias="warehouseName")
    part_id: str = Field(alias="partId")
    on_hand_quantity: Decimal = Field(alias="onHandQuantity")
    reserved_quantity: Decimal = Field(alias="reservedQuantity")
    available_quantity: Decimal = Field(alias="availableQuantity")
    in_transit_quantity: Decimal = Field(alias="inTransitQuantity")
    eligible_inbound_quantity: Decimal | None = Field(
        default=None,
        alias="eligibleInboundQuantity",
    )
    eligible_incoming_transfer_quantity: Decimal | None = Field(
        default=None,
        alias="eligibleIncomingTransferQuantity",
    )
    committed_outgoing_transfer_quantity: Decimal | None = Field(
        default=None,
        alias="committedOutgoingTransferQuantity",
    )
    projected_available_by_required_date: Decimal | None = Field(
        default=None,
        alias="projectedAvailableByRequiredDate",
    )
    safety_stock_quantity: Decimal | None = Field(
        default=None,
        alias="safetyStockQuantity",
    )
    surplus_above_safety_stock: Decimal | None = Field(
        default=None,
        alias="surplusAboveSafetyStock",
    )
    inventory_updated_at: datetime | None = Field(
        default=None,
        alias="inventoryUpdatedAt",
    )
    required_by_date: date | None = Field(default=None, alias="requiredByDate")
    warnings: list[str] = Field(default_factory=list)
