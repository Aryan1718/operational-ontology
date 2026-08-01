"""Pydantic schemas for ontology action execution."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from app.schemas.common import ApiBaseModel


class ActionExecutionRequest(ApiBaseModel):
    """Strict generic request body for public ontology action execution."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    parameters: dict[str, Any] = Field(default_factory=dict)


class ActionExecutionResponse(ApiBaseModel):
    """Shared successful payload returned from the action runtime."""

    action_name: str = Field(alias="actionName")
    result: Any
    warnings: list[str] = Field(default_factory=list)


class GenerateMitigationPlanParameters(ApiBaseModel):
    """Stable public input for generateMitigationPlan."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    risk_event_id: str = Field(alias="riskEventId", min_length=1)
    strategy_preference: str | None = Field(alias="strategyPreference", default=None)
    notes: str | None = Field(default=None)


class GenerateMitigationPlanResult(ApiBaseModel):
    """Created draft mitigation plan summary."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mitigation_plan_id: str = Field(alias="mitigationPlanId")
    risk_event_id: str = Field(alias="riskEventId")
    status: str
    strategy: str
    summary: str
    confidence_score: Decimal = Field(alias="confidenceScore")
    estimated_cost: Decimal = Field(alias="estimatedCost")
    generated_by: str = Field(alias="generatedBy")
    step_ids: list[str] = Field(alias="stepIds", default_factory=list)
    step_count: int = Field(alias="stepCount", ge=0)
    created_at: datetime = Field(alias="createdAt")
    warnings: list[str] = Field(default_factory=list)


class ApproveMitigationPlanParameters(ApiBaseModel):
    """Stable public input for approveMitigationPlan."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mitigation_plan_id: str = Field(alias="mitigationPlanId", min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reason must not be empty.")
        return normalized


class ApproveMitigationPlanResult(ApiBaseModel):
    """Approved mitigation plan summary."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mitigation_plan_id: str = Field(alias="mitigationPlanId")
    previous_status: str = Field(alias="previousStatus")
    new_status: str = Field(alias="newStatus")
    approved_by: str = Field(alias="approvedBy")
    approved_at: datetime = Field(alias="approvedAt")
    approved_estimated_cost: Decimal | None = Field(alias="approvedEstimatedCost", default=None)
    warnings: list[str] = Field(default_factory=list)


class ReallocateInventoryParameters(ApiBaseModel):
    """Stable public input for reallocateInventory."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mitigation_plan_id: str = Field(alias="mitigationPlanId", min_length=1)
    from_warehouse_id: str = Field(alias="fromWarehouseId", min_length=1)
    to_warehouse_id: str = Field(alias="toWarehouseId", min_length=1)
    part_id: str = Field(alias="partId", min_length=1)
    quantity: Decimal = Field(gt=0)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _validate_reallocation_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reason must not be empty.")
        return normalized


class ReallocatedInventoryPosition(ApiBaseModel):
    """Updated inventory position summary returned by reallocateInventory."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    inventory_position_id: str = Field(alias="inventoryPositionId")
    warehouse_id: str = Field(alias="warehouseId")
    previous_quantity: Decimal = Field(alias="previousQuantity")
    new_quantity: Decimal = Field(alias="newQuantity")


class ReallocateInventoryResult(ApiBaseModel):
    """Atomic inventory reallocation result."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    mitigation_plan_id: str = Field(alias="mitigationPlanId")
    part_id: str = Field(alias="partId")
    transferred_quantity: Decimal = Field(alias="transferredQuantity")
    source_inventory: ReallocatedInventoryPosition = Field(alias="sourceInventory")
    destination_inventory: ReallocatedInventoryPosition = Field(alias="destinationInventory")
    updated_source_quantity: Decimal = Field(alias="updatedSourceQuantity")
    updated_destination_quantity: Decimal = Field(alias="updatedDestinationQuantity")
    warnings: list[str] = Field(default_factory=list)


class ExpeditePurchaseOrderParameters(ApiBaseModel):
    """Stable public input for expeditePurchaseOrder."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    purchase_order_id: str = Field(alias="purchaseOrderId", min_length=1)
    new_expected_delivery_date: date = Field(alias="newExpectedDeliveryDate")
    additional_cost: Decimal = Field(alias="additionalCost", ge=0)
    mitigation_plan_id: str = Field(alias="mitigationPlanId", min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _validate_expedite_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reason must not be empty.")
        return normalized


class ExpeditePurchaseOrderResult(ApiBaseModel):
    """Updated purchase-order expedite result."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    purchase_order_id: str = Field(alias="purchaseOrderId")
    mitigation_plan_id: str = Field(alias="mitigationPlanId")
    mitigation_step_id: str = Field(alias="mitigationStepId")
    previous_expected_delivery_date: date = Field(alias="previousExpectedDeliveryDate")
    new_expected_delivery_date: date = Field(alias="newExpectedDeliveryDate")
    additional_cost: Decimal = Field(alias="additionalCost")
    expedited: bool
    warnings: list[str] = Field(default_factory=list)
