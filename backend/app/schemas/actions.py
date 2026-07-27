"""Pydantic schemas for ontology action execution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field

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
