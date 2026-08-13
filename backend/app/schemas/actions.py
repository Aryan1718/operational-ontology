"""Pydantic schemas for ontology action execution."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.models.action_execution import ActionExecutionInvocationMode, ActionExecutionStatus
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


class ActionExecutionActorSummary(ApiBaseModel):
    """Compact actor identity summary included in execution history responses."""

    actor_id: str = Field(alias="actorId")
    actor_role: str = Field(alias="actorRole")


class ActionExecutionSummary(ApiBaseModel):
    """Compact public action execution history summary."""

    execution_id: str = Field(alias="executionId")
    action_type_id: str = Field(alias="actionTypeId")
    status: ActionExecutionStatus
    actor: ActionExecutionActorSummary
    invocation_mode: ActionExecutionInvocationMode = Field(alias="invocationMode")
    parent_execution_id: str | None = Field(alias="parentExecutionId", default=None)
    started_at: datetime = Field(alias="startedAt")
    completed_at: datetime | None = Field(alias="completedAt", default=None)
    failure_code: str | None = Field(alias="failureCode", default=None)
    failure_message: str | None = Field(alias="failureMessage", default=None)


class ActionExecutionListResponse(ApiBaseModel):
    """Paginated action execution history response payload."""

    executions: list[ActionExecutionSummary] = Field(default_factory=list)


class ActionExecutionSearchRequest(ApiBaseModel):
    """Structured action execution history search request."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    action_type_id: str | None = Field(alias="actionTypeId", default=None)
    status: str | None = None
    actor_id: str | None = Field(alias="actorId", default=None)
    parent_execution_id: str | None = Field(alias="parentExecutionId", default=None)
    object_type: str | None = Field(alias="objectType", default=None)
    object_id: str | None = Field(alias="objectId", default=None)
    started_at_from: datetime | None = Field(alias="startedAtFrom", default=None)
    started_at_to: datetime | None = Field(alias="startedAtTo", default=None)
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator(
        "action_type_id",
        "status",
        "actor_id",
        "parent_execution_id",
        "object_type",
        "object_id",
    )
    @classmethod
    def _validate_optional_string_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Filter values must not be empty.")
        return normalized

    @model_validator(mode="after")
    def _validate_started_at_range(self) -> "ActionExecutionSearchRequest":
        if (
            self.started_at_from is not None
            and self.started_at_to is not None
            and self.started_at_from > self.started_at_to
        ):
            raise ValueError("startedAtFrom must be less than or equal to startedAtTo.")
        return self


class ActionExecutionSearchResponse(ApiBaseModel):
    """Paginated action execution search response payload."""

    items: list[ActionExecutionSummary] = Field(default_factory=list)
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class ActionExecutionDetailResponse(ApiBaseModel):
    """One persisted governed action execution."""

    execution_id: str = Field(alias="executionId")
    action_type_id: str = Field(alias="actionTypeId")
    action_version: str = Field(alias="actionVersion")
    status: ActionExecutionStatus
    actor: ActionExecutionActorSummary
    invocation_mode: ActionExecutionInvocationMode = Field(alias="invocationMode")
    parent_execution_id: str | None = Field(alias="parentExecutionId", default=None)
    reason: str | None = None
    started_at: datetime = Field(alias="startedAt")
    completed_at: datetime | None = Field(alias="completedAt", default=None)
    result_payload: Any | None = Field(alias="resultPayload", default=None)
    failure_code: str | None = Field(alias="failureCode", default=None)
    failure_message: str | None = Field(alias="failureMessage", default=None)
    affected_objects: list[dict[str, str]] | None = Field(alias="affectedObjects", default=None)


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
